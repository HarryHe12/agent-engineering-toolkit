"""Exercise the executable hook with isolated state and broken installations."""
import hashlib,json,pathlib,shutil,subprocess,tempfile,unittest

BASE=pathlib.Path(__file__).resolve().parent

class FailurePathTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.home=pathlib.Path(self.temp.name)
        self.engine=self.home/'engine'; self.engine.mkdir()
        self.project=self.home/'project'; self.project.mkdir()
        shutil.copy(BASE/'hook.py',self.engine/'hook.py')
        for name in ['scan.mjs','python_metrics.py','policies.json','node_modules']:
            (self.engine/name).symlink_to(BASE/name)
        self.event={'session_id':'isolated-failure-test','turn_id':'turn-one','cwd':str(self.project),'hook_event_name':'PreToolUse'}
    def tearDown(self):
        self.temp.cleanup()
    def invoke(self,kind,**fields):
        self.event.update(fields,hook_event_name=kind)
        result=subprocess.run(['/usr/bin/python3',str(self.engine/'hook.py')],input=json.dumps(self.event),text=True,capture_output=True,timeout=20,check=True)
        self.assertEqual(result.stderr,'')
        return json.loads(result.stdout)
    def assert_recoverable(self):
        for kind in ['SessionStart','PreToolUse','PostToolUse']:
            result=self.invoke(kind)
            self.assertNotIn('decision',result)
            self.assertIn('unavailable',result['hookSpecificOutput']['additionalContext'])
        result=self.invoke('Stop')
        self.assertEqual(result['decision'],'block')
        for _ in range(3):
            result=self.invoke('Stop',stop_hook_active=True)
            self.assertFalse(result['continue'])
            self.assertNotIn('decision',result)
    def test_missing_scanner_preserves_diagnostics_and_bounds_stop(self):
        (self.engine/'scan.mjs').unlink()
        self.assert_recoverable()
    def test_integrity_failure_preserves_diagnostics_and_bounds_stop(self):
        policy=self.engine/'protected';policy.write_text('changed')
        (self.engine/'integrity.json').write_text(json.dumps({str(policy):hashlib.sha256(b'approved').hexdigest()}))
        self.assert_recoverable()
    def test_corrupt_session_state_can_be_diagnosed(self):
        self.invoke('PreToolUse')
        for path in (self.engine/'state').glob('*-*.json'):
            if not path.name.startswith('baseline-'):path.write_text('{incomplete')
        result=self.invoke('PostToolUse')
        self.assertIn('unavailable',result['hookSpecificOutput']['additionalContext'])
        self.assertEqual(self.invoke('Stop')['decision'],'block')
        self.assertFalse(self.invoke('Stop',stop_hook_active=True)['continue'])
    def test_unwritable_recovery_state_reports_failure_without_loop(self):
        (self.engine/'state').write_text('not a directory')
        self.assertNotIn('decision',self.invoke('PreToolUse'))
        result=self.invoke('Stop')
        self.assertFalse(result['continue'])
        self.assertIn('did not pass',result['systemMessage'])
    def test_failure_then_repair_keeps_baseline_and_clears_stop(self):
        self.invoke('PreToolUse')
        baselines=list((self.engine/'state').glob('baseline-*.json'))
        before={p:p.read_bytes() for p in baselines}
        source=self.project/'app.js';source.write_text('new Buffer(1);\n')
        result=self.invoke('PostToolUse')
        self.assertNotIn('decision',result)
        self.assertEqual(self.invoke('Stop')['decision'],'block')
        self.assertFalse(self.invoke('Stop',stop_hook_active=True)['continue'])
        for p,content in before.items():self.assertEqual(p.read_bytes(),content)
        source.write_text('const value = 1;\n')
        self.assertEqual(self.invoke('PostToolUse'),{})
        self.assertEqual(self.invoke('Stop'),{})
    def test_changing_errors_and_roots_cannot_extend_active_retry(self):
        self.invoke('PreToolUse')
        source=self.project/'app.js';source.write_text('new Buffer(1);\n')
        self.assertEqual(self.invoke('Stop')['decision'],'block')
        for i in range(3):
            source.write_text('new Buffer(%d);\n'%(i+2))
            result=self.invoke('Stop',stop_hook_active=True)
            self.assertFalse(result['continue'])
        self.assertEqual(self.invoke('Stop',turn_id='turn-two',stop_hook_active=False)['decision'],'block')
    def test_subagent_retry_is_bounded(self):
        self.invoke('PreToolUse')
        (self.project/'app.js').write_text('new Buffer(1);\n')
        self.assertEqual(self.invoke('SubagentStop',agent_id='child')['decision'],'block')
        self.assertFalse(self.invoke('SubagentStop',stop_hook_active=True)['continue'])
    def test_imported_source_is_reported_without_rewriting_baseline(self):
        self.invoke('PreToolUse')
        baselines=list((self.engine/'state').glob('baseline-*.json'))
        before={p:p.read_bytes() for p in baselines}
        source=self.project/'app.js';source.write_text('new Buffer(1);\n')
        self.event.update(session_id='after-authorized-git-update')
        self.invoke('PreToolUse')
        read=self.invoke('PostToolUse')
        self.assertNotIn('decision',read)
        self.assertIn('pre-existing',read['hookSpecificOutput']['additionalContext'])
        final=self.invoke('Stop')
        self.assertNotIn('decision',final)
        self.assertIn('not certification',final['systemMessage'])
        for p,content in before.items():self.assertEqual(p.read_bytes(),content)
        self.invoke('PreToolUse')
        source.write_text('new Buffer(1);\nnew Buffer(2);\n')
        self.assertEqual(self.invoke('Stop')['decision'],'block')
        self.event.update(session_id='pending-import-edit-next-chat',stop_hook_active=False)
        self.invoke('PreToolUse')
        self.assertNotEqual(self.invoke('Stop').get('decision'),'block')
    def test_new_root_cannot_restart_an_active_stop_retry(self):
        self.invoke('PreToolUse')
        (self.project/'app.js').write_text('new Buffer(1);\n')
        self.assertEqual(self.invoke('Stop')['decision'],'block')
        second=self.home/'second-project';second.mkdir()
        self.invoke('PreToolUse',cwd=str(second),stop_hook_active=True)
        (second/'other.js').write_text('new Buffer(2);\n')
        result=self.invoke('Stop')
        self.assertNotIn('decision',result)
        self.assertFalse(result['continue'])
        self.assertIn('other.js',result['systemMessage'])
        self.event.update(session_id='pending-edit-next-chat',stop_hook_active=False)
        self.invoke('PreToolUse')
        self.assertNotEqual(self.invoke('Stop').get('decision'),'block')

if __name__=='__main__':unittest.main()
