"""Run installed Codex against a loopback response fixture and isolated hooks.

No real model, credentials, user hook activation or external API is involved.
"""
import http.server,json,os,pathlib,shutil,subprocess,tempfile,threading,unittest

BASE=pathlib.Path(__file__).resolve().parent
CODEX=shutil.which('codex')

def stream_items(items,number):
    response={'id':'resp_'+str(number),'object':'response','status':'in_progress','output':[]}
    events=[{'type':'response.created','response':response}]
    for index,item in enumerate(items):
        events.append({'type':'response.output_item.added','output_index':index,'item':item})
        if item['type']=='message':
            events.append({'type':'response.output_text.delta','item_id':item['id'],'output_index':index,'content_index':0,'delta':item['content'][0]['text']})
        events.append({'type':'response.output_item.done','output_index':index,'item':item})
    response=dict(response,status='completed',output=items,usage={'input_tokens':1,'output_tokens':1,'total_tokens':2})
    events.append({'type':'response.completed','response':response})
    return ''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events).encode()

class FixtureServer(http.server.ThreadingHTTPServer):
    def __init__(self,project,mode):
        super().__init__(('127.0.0.1',0),FixtureHandler)
        self.project=project; self.mode=mode; self.requests=[]; self.failure=None
    def next_items(self,payload):
        self.requests.append(payload); number=len(self.requests)
        tools=[t.get('name') for t in payload.get('tools',[])]
        if number>6:raise RuntimeError('Unexpected runtime retry loop')
        if number==1:
            if 'exec_command' not in tools:raise RuntimeError('Expected exec_command; offered '+str(tools))
            command='cat read-marker.txt'
            if self.mode not in ('clean','inherited','pending','foreign'):command="printf 'new Buffer(1);\\n' > app.js; cat read-marker.txt"
            arguments={'cmd':command,'workdir':str(self.project),'yield_time_ms':1000,'max_output_tokens':1000}
            return [{'type':'function_call','id':'fc_1','call_id':'call_1','name':'exec_command','arguments':json.dumps(arguments),'status':'completed'}]
        if self.mode=='foreign' and number==2:
            (self.project/'foreign.js').write_text('new Buffer(1);\n')
            other=self.project.parent/'other';other.mkdir()
            (other/'marker.txt').write_text('OTHER_READ_PRESERVED')
            arguments={'cmd':'cat marker.txt','workdir':str(other),'max_output_tokens':1000}
            return [{'type':'function_call','id':'fc_other','call_id':'call_other','name':'exec_command','arguments':json.dumps(arguments),'status':'completed'}]
        if self.mode=='repair' and number==3:
            arguments={'cmd':"printf 'const value = 1;\\n' > app.js; cat read-marker.txt",'workdir':str(self.project),'yield_time_ms':1000,'max_output_tokens':1000}
            return [{'type':'function_call','id':'fc_repair','call_id':'call_repair','name':'exec_command','arguments':json.dumps(arguments),'status':'completed'}]
        return [{'type':'message','id':'msg_'+str(number),'role':'assistant','phase':'final_answer','status':'completed','content':[{'type':'output_text','text':'Fixture completed; consult hook verification status.','annotations':[]}]}]

class FixtureHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        try:
            payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            body=stream_items(self.server.next_items(payload),len(self.server.requests))
            self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        except Exception as error:
            self.server.failure=str(error);self.send_error(500,str(error))

class RuntimeTests(unittest.TestCase):
    def prepare(self,home,project,engine,mode):
        home.mkdir();project.mkdir();engine.mkdir()
        shutil.copy(BASE/'hook.py',engine/'hook.py')
        for name in ['scan.mjs','python_metrics.py','policies.json','node_modules']:(engine/name).symlink_to(BASE/name)
        if mode=='unavailable':(engine/'scan.mjs').unlink()
        if mode in ('inherited','pending'):
            event={'session_id':'before-import','cwd':str(project),'hook_event_name':'PreToolUse'}
            subprocess.run(['/usr/bin/python3',str(engine/'hook.py')],input=json.dumps(event),text=True,capture_output=True,check=True)
            (project/'app.js').write_text('new Buffer(1);\n')
            if mode=='pending':
                event['hook_event_name']='PostToolUse'
                subprocess.run(['/usr/bin/python3',str(engine/'hook.py')],input=json.dumps(event),text=True,capture_output=True,check=True)
        (project/'read-marker.txt').write_text('READ_RESULT_PRESERVED\n')
        log=home/'events.jsonl';wrapper=home/'hook_wrapper.py'
        wrapper.write_text('import json,subprocess,sys\nfrom pathlib import Path\nevent=json.load(sys.stdin)\np=subprocess.run(["/usr/bin/python3",'+repr(str(engine/'hook.py'))+'],input=json.dumps(event),text=True,capture_output=True,check=True)\nwith Path('+repr(str(log))+').open("a") as stream: stream.write(json.dumps({"event":event,"output":json.loads(p.stdout)})+"\\n")\nprint(p.stdout)\n')
        command='/usr/bin/python3 '+str(wrapper)
        hooks={kind:[{'matcher':'.*','hooks':[{'type':'command','command':command,'timeout':20}]}] for kind in ['SessionStart','PreToolUse','PostToolUse','Stop','SubagentStop']}
        (home/'hooks.json').write_text(json.dumps({'hooks':hooks}))
        return log
    def run_case(self,mode):
        with tempfile.TemporaryDirectory(prefix='guard-runtime-') as tmp:
            root=pathlib.Path(tmp);home=root/'home';project=root/'project';engine=root/'engine'
            log=self.prepare(home,project,engine,mode)
            server=FixtureServer(project,mode);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            config='''model = "gpt-6.2"
model_provider = "fixture"
approval_policy = "never"
sandbox_mode = "danger-full-access"
[features]
hooks = true
shell_snapshot = false
enable_request_compression = false
[model_providers.fixture]
name = "Loopback fixture"
wire_api = "responses"
requires_openai_auth = false
base_url = "http://127.0.0.1:%d/v1"
'''%server.server_port
            (home/'config.toml').write_text(config)
            env=dict(os.environ,CODEX_HOME=str(home));env.pop('OPENAI_API_KEY',None)
            try:
                process=subprocess.run([CODEX,'--no-daemon','exec','--ephemeral','--skip-git-repo-check','--dangerously-bypass-hook-trust','--json','-C',str(project),'Run the deterministic local hook fixture.'],env=env,text=True,capture_output=True,timeout=50)
            finally:server.shutdown();server.server_close();thread.join(timeout=3)
            self.assertIsNone(server.failure,server.failure)
            self.assertEqual(process.returncode,0,process.stderr[-4000:]+process.stdout[-4000:])
            events=[json.loads(line) for line in log.read_text().splitlines()]
            self.assertTrue(any(e['event']['hook_event_name']=='PreToolUse' for e in events),process.stderr)
            self.assertTrue(any(e['event']['hook_event_name']=='PostToolUse' for e in events))
            self.assertIn('READ_RESULT_PRESERVED',json.dumps(server.requests[1:]))
            stops=[e for e in events if e['event']['hook_event_name']=='Stop']
            self.assertTrue(stops)
            if mode=='clean':
                self.assertEqual(len(stops),1)
                self.assertNotIn('decision',stops[0]['output'])
                self.assertNotIn('continue',stops[0]['output'])
                self.assertIn('code verification not performed',stops[0]['output']['systemMessage'])
            elif mode in ('inherited','pending','foreign'):
                self.assertEqual(len(stops),1)
                self.assertNotIn('decision',stops[0]['output'])
                self.assertIn('pre-existing',stops[0]['output']['systemMessage'])
            elif mode=='repair':
                self.assertEqual(stops[0]['output'].get('decision'),'block')
                self.assertEqual(stops[-1]['output'],{})
                self.assertEqual((project/'app.js').read_text(),'const value = 1;\n')
            else:
                self.assertEqual(stops[0]['output'].get('decision'),'block')
                self.assertEqual(len(stops),2)
                self.assertFalse(stops[-1]['output']['continue'])
                self.assertTrue(stops[-1]['event']['stop_hook_active'])
            summary={'mode':mode,'requests':len(server.requests),'events':len(events),'stops':len(stops),'runtime_version':subprocess.check_output([CODEX,'--version'],text=True).strip(),'hook_results':[{'kind':e['event']['hook_event_name'],'stop_hook_active':e['event'].get('stop_hook_active'),'output':e['output']} for e in events]}
            if os.environ.get('GUARD_RUNTIME_REPORT_DIR'):
                reports=pathlib.Path(os.environ['GUARD_RUNTIME_REPORT_DIR']);reports.mkdir(mode=0o700,parents=True,exist_ok=True)
                (reports/(mode+'.json')).write_text(json.dumps(summary,indent=2)+'\n')
            return {key:summary[key] for key in ['mode','requests','events','stops']}
    def test_foreign_repository_is_not_owned_by_read_tool(self):print(self.run_case('foreign'))
    def test_pending_debt_in_same_root_is_not_adopted(self):print(self.run_case('pending'))
    def test_clean_read_keeps_original_output(self):print(self.run_case('clean'))
    def test_violation_is_reported_and_retry_stops(self):print(self.run_case('violation'))
    def test_repair_clears_final_gate(self):print(self.run_case('repair'))
    def test_missing_scanner_does_not_hide_read_or_loop(self):print(self.run_case('unavailable'))
    def test_imported_source_is_warned_without_false_continuation(self):print(self.run_case('inherited'))

if __name__=='__main__':unittest.main()
