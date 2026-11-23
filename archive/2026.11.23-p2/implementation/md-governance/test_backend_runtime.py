"""Installed Codex tool inventory, isolated loopback transport; no real model."""
import http.server
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch
import md_backend
import test_support
import md_context


class Server(http.server.ThreadingHTTPServer):
    def __init__(self,verdict):
        super().__init__(('127.0.0.1',0),Handler)
        self.requests=[]; self.verdict=verdict


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_POST(self):
        payload=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.requests.append(payload)
        item={'type':'message','id':'msg_1','role':'assistant','phase':'final_answer','status':'completed',
              'content':[{'type':'output_text','text':json.dumps(self.server.verdict),'annotations':[]}]}
        response={'id':'resp_1','object':'response','status':'in_progress','output':[]}
        events=[{'type':'response.created','response':response},
                {'type':'response.output_item.added','output_index':0,'item':item},
                {'type':'response.output_text.delta','item_id':'msg_1','output_index':0,'content_index':0,'delta':item['content'][0]['text']},
                {'type':'response.output_item.done','output_index':0,'item':item},
                {'type':'response.completed','response':dict(response,status='completed',output=[item],usage={'input_tokens':1,'output_tokens':1,'total_tokens':2})}]
        data=''.join('event: '+e['type']+'\ndata: '+json.dumps(e)+'\n\n' for e in events).encode()
        self.send_response(200);self.send_header('Content-Type','text/event-stream')
        self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)


@unittest.skipUnless(shutil.which('codex'),'native Codex CLI unavailable')
class BackendRuntimeTests(unittest.TestCase):
    def test_reviewer_has_no_executable_tools_or_parent_hooks(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); target=root/'AGENTS.md'; draft=root/'candidate.stage'; request=root/'request.txt'
            target.write_text('# Rules\n\nPreserve user work before editing source files.\n')
            draft.write_text(target.read_text()+'\nRun the existing checks after source behavior changes.\n')
            request.write_text('Add scoped behavior verification while preserving user work.')
            packet=md_context.build(target,draft,request)[2]
            expected=test_support.verdict(packet)
            server=Server(expected);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            def prepare(home):
                provider='model_provider = "fixture"\nmodel = "gpt-6.2"\n'
                suffix='\n[model_providers.fixture]\nname = "loopback"\nwire_api = "responses"\nrequires_openai_auth = false\nbase_url = "http://127.0.0.1:%d/v1"\n'%server.server_port
                (home/'config.toml').write_text(md_backend.configuration(provider)+suffix)
                return 'loopback'
            try:
                with patch('md_backend.prepare',side_effect=prepare):
                    verdict,execution=md_backend.invoke(packet,root/'result')
            finally:server.shutdown();server.server_close();thread.join(timeout=3)
            offered={t.get('name',t.get('type')) for p in server.requests for t in p.get('tools',[])}
            self.assertFalse(offered-{'request_user_input'},offered)
            self.assertNotIn('exec_command',offered)
            self.assertNotIn('view_image',offered)
            self.assertEqual(verdict,expected)
            self.assertFalse(execution['tools_used'])


class EventContractTests(unittest.TestCase):
    def test_tool_attempt_or_unknown_error_is_never_approval(self):
        for item in [{'type':'command_execution'},{'type':'error','message':'network failed'}]:
            text=json.dumps({'type':'item.completed','item':item})+'\n'+json.dumps({'type':'turn.completed','usage':{}})
            with self.assertRaises(ValueError):md_backend.parse_events(text)
