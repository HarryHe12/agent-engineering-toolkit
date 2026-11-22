"""Independent native Codex session: isolated rules, no author conversation or tools."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from md_verdict import policy,schema


def prepare(home):
    live=Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))
    auth=live/'auth.json'
    if not auth.exists(): raise ValueError('Independent reviewer unavailable: existing Codex login required; no API key requested.')
    shutil.copyfile(auth,home/'auth.json'); (home/'auth.json').chmod(0o600)
    text=(live/'config.toml').read_text() if (live/'config.toml').exists() else ''
    model=re.search(r'^model\s*=\s*"([^"]+)"',text,re.M)
    setting=('model = '+json.dumps(model[1])+'\n') if model else ''
    (home/'config.toml').write_text(configuration(setting))
    return model[1] if model else 'account default'


def configuration(setting=''):
    return setting+'approval_policy = "never"\nsandbox_mode = "read-only"\nweb_search = "disabled"\n[features]\nhooks = false\nshell_snapshot = false\nshell_tool = false\nunified_exec = false\napps = false\nplugins = false\nmulti_agent = false\nview_image = false\ngoals = false\n'

def parse_events(text):
    rows=[]
    for line in text.splitlines():
        try: rows.append(json.loads(line))
        except ValueError: continue
    items=[row.get('item',{}) for row in rows if row.get('type') in ('item.started','item.completed')]
    warnings=[]
    for item in items:
        if item.get('type') in ('agent_message','reasoning'): continue
        message=item.get('message','')
        if item.get('type')=='error' and message.startswith('Model metadata for `') and 'Defaulting to fallback metadata' in message:
            warnings.append(message)
            continue
        raise ValueError('Independent reviewer attempted tools or failed: '+str(item.get('type')))
    completed=[row for row in rows if row.get('type')=='turn.completed']
    if not completed: raise ValueError('Independent reviewer did not complete.')
    return completed[-1].get('usage',{}),warnings


def invoke(packet,destination):
    executable=shutil.which('codex')
    if not executable: raise ValueError('Independent reviewer unavailable: Codex CLI missing.')
    destination.mkdir(parents=True,mode=0o700,exist_ok=True)
    prompt=json.dumps({'role':'Independent instruction reviewer. Return JSON only; no tools.',
                       'policy':policy(),'review_input':packet},ensure_ascii=False)
    started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='md-review-') as directory:
        home=Path(directory); model=prepare(home)
        output=home/'verdict.json'; schema_path=home/'schema.json'
        schema_path.write_text(json.dumps(schema()))
        command=[executable,'--no-daemon','exec','--ephemeral','--skip-git-repo-check','--json',
                 '-C',str(home),'-s','read-only','--output-schema',str(schema_path),'-o',str(output),'-']
        env=dict(os.environ,CODEX_HOME=str(home))
        env.pop('OPENAI_API_KEY',None); env.pop('CODEX_API_KEY',None)
        try:
            result=subprocess.run(command,input=prompt,env=env,text=True,capture_output=True,timeout=360)
            usage,warnings=parse_events(result.stdout)
            if result.returncode or not output.exists(): raise ValueError('Independent reviewer failed; candidate remains unpublished.')
            verdict=json.loads(output.read_text())
            (destination/'events.jsonl').write_text(result.stdout)
        finally:
            (home/'auth.json').unlink(missing_ok=True)
    execution={'provider':'native Codex CLI','model':model,'usage':usage,'seconds':round(time.monotonic()-started,3),
               'isolated_conversation':True,'tools_used':False,'returncode':result.returncode,'runtime_warnings':warnings}
    return verdict,execution
