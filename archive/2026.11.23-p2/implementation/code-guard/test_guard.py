import json,pathlib,subprocess,tempfile,unittest,uuid
BASE=pathlib.Path(__file__).resolve().parent
class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=pathlib.Path(self.temp.name); self.sid='test-'+str(uuid.uuid4())
    def tearDown(self):
        import hashlib
        prefix=hashlib.sha256(self.sid.encode()).hexdigest()[:20]
        for p in (BASE/'state').glob(prefix+'-*'): p.unlink()
        rootkey=hashlib.sha256(str(self.root.resolve()).encode()).hexdigest()
        for p in (BASE/'state').glob('*'+rootkey+'*'): p.unlink()
        self.temp.cleanup()
    def hook(self,kind,root=None):
        p=subprocess.run(['/usr/bin/python3',str(BASE/'hook.py')],input=json.dumps({'session_id':self.sid,'cwd':str(root or self.root),'hook_event_name':kind}),text=True,capture_output=True)
        self.assertEqual(p.returncode,0,p.stderr)
        result=json.loads(p.stdout)
        if kind=='PostToolUse' and 'FAILED' in result.get('hookSpecificOutput',{}).get('additionalContext',''):
            return {'decision':'block','reason':result['hookSpecificOutput']['additionalContext']}
        if kind=='PreToolUse': self.assertEqual(result,{},result)
        return result
    def write(self,text,name='app.js'): (self.root/name).write_text(text)
    def assertBlocked(self,result,needle):
        self.assertEqual(result.get('decision'),'block',result); self.assertIn(needle,result['reason'])
    def test_new_long_function_rejected_then_fixed(self):
        self.hook('PreToolUse'); self.write('function work(){\n'+'console.log(1);\n'*81+'}\n')
        self.assertBlocked(self.hook('PostToolUse'),'too many lines')
        self.write('function work(){ return 1; }\n'); self.assertEqual(self.hook('Stop'),{})
    def test_legacy_cannot_grow_and_can_shrink(self):
        self.write('function work(){\n'+'console.log(1);\n'*90+'}\n'); self.hook('PreToolUse')
        self.write('function work(){\n'+'console.log(1);\n'*91+'}\n'); self.assertBlocked(self.hook('PostToolUse'),'too many lines')
        self.write('function work(){\n'+'console.log(1);\n'*85+'}\n'); self.assertEqual(self.hook('Stop'),{})
    def test_deprecated_and_disable_rejected(self):
        self.hook('PreToolUse'); self.write('/* eslint-disable */\nconst x=new Buffer(4);\n')
        r=self.hook('PostToolUse'); self.assertBlocked(r,'Buffer'); self.assertIn('override',r['reason'])
    def test_unsupported_not_grandfathered_after_change(self):
        self.write('package main\n','a.go'); self.hook('PreToolUse'); self.write('package main\nfunc main() {}\n','a.go')
        self.assertBlocked(self.hook('Stop'),'No checker')
    def test_typescript_and_python(self):
        self.hook('PreToolUse'); self.write('const x: number = 1;\n','a.ts'); self.write('def f():\n    return 1\n','a.py')
        self.assertEqual(self.hook('PostToolUse'),{})
        self.hook('PreToolUse'); self.write('def f(:\n','a.py'); self.assertBlocked(self.hook('Stop'),'invalid syntax')
    def test_committing_does_not_erase_failure(self):
        subprocess.run(['git','init','-q',str(self.root)],check=True); self.hook('PreToolUse')
        self.write('new Buffer(2);\n'); subprocess.run(['git','-C',str(self.root),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.root),'-c','user.name=Test','-c','user.email=test@example.invalid','commit','-qm','fixture'],check=True)
        self.assertBlocked(self.hook('Stop'),'Buffer')
    def test_final_checks_other_working_directory(self):
        self.hook('PreToolUse'); self.write('new Buffer(2);\n')
        with tempfile.TemporaryDirectory() as elsewhere: self.assertBlocked(self.hook('Stop',pathlib.Path(elsewhere)),'Buffer')
    def test_one_line_statement_compression_is_rejected(self):
        self.hook('PreToolUse'); self.write('function x(){'+'console.log(1);'*51+'}')
        self.assertBlocked(self.hook('Stop'),'statements')
    def test_complexity_and_depth(self):
        self.hook('PreToolUse'); self.write('function x(a){'+''.join('if(a==%s){return %s;}'%(i,i) for i in range(16))+'}')
        self.assertBlocked(self.hook('PostToolUse'),'complexity')
        self.write('function x(a){'+'if(a){'*5+'return a;'+'}'*6)
        self.assertBlocked(self.hook('Stop'),'deeply')
    def test_deprecated_require_is_rejected(self):
        self.hook('PreToolUse'); self.write("const old=require('sys');\n")
        self.assertBlocked(self.hook('Stop'),'Deprecated')
    def test_lint_words_inside_strings_are_not_suppressions(self):
        self.hook('PreToolUse'); self.write('const example="eslint-disable";\n')
        self.assertEqual(self.hook('Stop'),{})
    def test_new_source_symlink_is_not_silently_skipped(self):
        self.hook('PreToolUse'); (self.root/'alias.js').symlink_to('/nonexistent/source.js')
        self.assertBlocked(self.hook('Stop'),'symlink')
    def test_new_chat_does_not_adopt_other_chat_failure(self):
        self.hook('PreToolUse'); self.write('new Buffer(2);\n')
        self.assertBlocked(self.hook('PostToolUse'),'Buffer')
        old=self.sid; self.sid='test-'+str(uuid.uuid4())
        self.hook('PreToolUse'); self.assertNotEqual(self.hook('Stop').get('decision'),'block')
        import hashlib
        prefix=hashlib.sha256(old.encode()).hexdigest()[:20]
        for p in (BASE/'state').glob(prefix+'-*'): p.unlink()
    def test_file_size_and_javascript_parse_errors(self):
        self.hook('PreToolUse'); self.write('const a = ;\n')
        self.assertBlocked(self.hook('PostToolUse'),'Parsing error')
        self.write('console.log(1);\n'*501)
        self.assertBlocked(self.hook('Stop'),'too many lines')
    def test_project_retirement_mapping(self):
        import shutil
        with tempfile.TemporaryDirectory() as engine:
            engine=pathlib.Path(engine)
            shutil.copy(BASE/'scan.mjs',engine/'scan.mjs')
            (engine/'node_modules').symlink_to(BASE/'node_modules',target_is_directory=True)
            (engine/'policies.json').write_text(json.dumps({'retiredModules':[{'root':str(self.root.resolve()),'module':'./old.js','replacement':'./new.js'}]}))
            self.write("const x=require('./old.js');\n")
            p=subprocess.run([__import__('shutil').which('node'),str(engine/'scan.mjs')],input=json.dumps({'root':str(self.root.resolve())}),text=True,capture_output=True)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('Retired module ./old.js. Use ./new.js.',p.stdout)
    def test_changed_guard_installation_blocks(self):
        import shutil,hashlib
        with tempfile.TemporaryDirectory() as engine:
            engine=pathlib.Path(engine); shutil.copy(BASE/'hook.py',engine/'hook.py')
            protected=engine/'policy.txt'; protected.write_text('approved')
            (engine/'integrity.json').write_text(json.dumps({str(protected):hashlib.sha256(protected.read_bytes()).hexdigest()}))
            protected.write_text('modified')
            p=subprocess.run(['/usr/bin/python3',str(engine/'hook.py')],input=json.dumps({'hook_event_name':'Stop','cwd':str(self.root)}),text=True,capture_output=True)
            self.assertBlocked(json.loads(p.stdout),'Guard installation changed')
    def test_successful_reduction_cannot_regress(self):
        self.write('function x(){\n'+'console.log(1);\n'*90+'}'); self.hook('PreToolUse')
        self.write('function x(){\n'+'console.log(1);\n'*85+'}'); self.assertEqual(self.hook('PostToolUse'),{})
        self.hook('PreToolUse'); self.write('function x(){\n'+'console.log(1);\n'*86+'}'); self.assertBlocked(self.hook('Stop'),'too many lines')
    def test_instruction_edit_without_review_is_blocked(self):
        self.write('# Instructions\n\nKeep this fixture scoped to its temporary project.\n','AGENTS.md')
        self.hook('PreToolUse')
        self.write('# Instructions\n\nKeep this fixture scoped to its temporary project.\nDo not publish without a version-bound review.\n','AGENTS.md')
        self.assertBlocked(self.hook('Stop'),'version-bound semantic review')
    def test_managed_instruction_failure_is_not_grandfathered(self):
        import importlib.util
        spec=importlib.util.spec_from_file_location('guard_under_test',BASE/'hook.py')
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        row={'hash':'same','metrics':{'md:managed-review-required':{'value':1,'count':1,'line':1,'message':'Missing valid review'}}}
        self.assertTrue(module.failures({'@md:test':row},{'@md:test':row}))
    def test_link_target_deletion_is_detected_without_editing_doc(self):
        self.write('exists','target.txt'); self.write('# Instructions\n\nRead [reference](target.txt) before changing this fixture.\n','AGENTS.md')
        self.hook('PreToolUse'); (self.root/'target.txt').unlink()
        self.assertBlocked(self.hook('PostToolUse'),'Missing local link target')
        self.write('restored','target.txt')
        result=self.hook('Stop')
        self.assertNotIn('decision',result)
        self.assertIn('code verification not performed',result['systemMessage'])
    def test_nested_repository_is_delegated_but_still_enforced(self):
        self.hook('PreToolUse'); nested=self.root/'imported';nested.mkdir()
        subprocess.run(['git','init','-q',str(nested)],check=True)
        code='function x(){\n'+'console.log(1);\n'*90+'}'
        (nested/'old.js').write_text(code)
        self.hook('PreToolUse',nested)
        self.assertIn('verification not performed',self.hook('PostToolUse')['hookSpecificOutput']['additionalContext'])
        (nested/'old.js').write_text(code.replace('}', 'console.log(2);\n}'))
        self.assertBlocked(self.hook('PostToolUse',nested),'too many lines')
        self.assertBlocked(self.hook('Stop'),'too many lines')
    def test_clean_conversation_does_not_require_baseline(self):
        result=self.hook('Stop')
        self.assertNotIn('decision',result)
        self.assertIn('no registered roots; verification not performed',result['systemMessage'])
    def test_real_event_chain_keeps_diagnostics_without_retry_loop(self):
        self.hook('PreToolUse'); self.write('new Buffer(2);\n')
        event={'session_id':self.sid,'cwd':str(self.root),'hook_event_name':'PostToolUse'}
        def invoke():
            p=subprocess.run(['/usr/bin/python3',str(BASE/'hook.py')],input=json.dumps(event),text=True,capture_output=True,check=True)
            return json.loads(p.stdout)
        self.assertNotIn('decision',invoke())
        event['hook_event_name']='Stop'
        self.assertBlocked(invoke(),'Buffer')
        event['stop_hook_active']=True
        result=invoke()
        self.assertNotIn('decision',result)
        self.assertIn('not a passing verification',result['systemMessage'])
        self.write('new Buffer(3);\n')
        result=invoke()
        self.assertFalse(result['continue'])
        event.update(turn_id='next-user-turn',stop_hook_active=False)
        self.assertBlocked(invoke(),'Buffer')
        self.write('const safe = 3;\n')
        self.assertEqual(invoke(),{})
class RecoveryTests(unittest.TestCase):
    def setUp(self):
        import hook
        self.guard=hook
        self.metric={'value':1,'count':1,'line':1,'message':'review required'}
    def test_unchanged_legacy_instruction_diagnostic_drift(self):
        old={'hash':'original','metrics':{'md:review-required':self.metric}}
        new={'hash':'original','metrics':{'md:review-required':self.metric,'other':dict(self.metric,value=0,count=0)}}
        self.assertEqual(self.guard.failures({'doc':new},{'doc':old}),[])
        new['hash']='edited'
        self.assertTrue(self.guard.failures({'doc':new},{'doc':old}))
    def test_read_feedback_preserves_tool_output_and_stop_gate(self):
        data={}; current={'source':{'hash':'bad'}}
        feedback=self.guard.failure_outcome('PostToolUse',['bad source'],current,data)
        self.assertNotIn('decision',feedback)
        self.assertIn('bad source',feedback['hookSpecificOutput']['additionalContext'])
        self.assertEqual(self.guard.failure_outcome('Stop',['bad source'],current,data)['decision'],'block')
    def test_identical_stop_failure_has_bounded_retries(self):
        data={}; current={'source':{'hash':'bad'}}
        self.assertEqual(self.guard.failure_outcome('Stop',['bad'],current,data)['decision'],'block')
        for _ in range(20):
            result=self.guard.failure_outcome('Stop',['bad'],current,data)
            self.assertNotIn('decision',result)
            self.assertIn('not a passing verification',result['systemMessage'])
        current['source']['hash']='different bad change'
        self.assertEqual(self.guard.failure_outcome('Stop',['bad'],current,data)['decision'],'block')
    def test_subagent_stop_has_same_retry_bound(self):
        data={}; current={'source':{'hash':'bad'}}
        self.assertEqual(self.guard.failure_outcome('SubagentStop',['bad'],current,data)['decision'],'block')
        self.assertNotIn('decision',self.guard.failure_outcome('SubagentStop',['bad'],current,data))

if __name__=='__main__': unittest.main()
