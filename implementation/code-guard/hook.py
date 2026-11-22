#!/usr/bin/python3
"""Local synchronous Codex gates. Store hashes/diagnostics, never source contents."""
import fcntl,shutil,hashlib,json,os,pathlib,re,subprocess,sys,tempfile
BASE=pathlib.Path(__file__).resolve().parent
NODE=os.environ.get('CODEX_GUARD_NODE') or shutil.which('node')
STATE=BASE/'state'
def verify_integrity():
    manifest=BASE/'integrity.json'
    if not manifest.exists(): return
    for name,expected in json.loads(manifest.read_text()).items():
        target=pathlib.Path(name)
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=expected:
            raise RuntimeError('Guard installation changed: '+name+'. Restore the verified version or perform explicitly authorized guard maintenance.')
def run_scan(root,previous,delegated_roots=()):
    if not NODE: raise RuntimeError('Node executable missing; configure CODEX_GUARD_NODE.')
    env=dict(os.environ)
    env.setdefault('CODEX_HOME',str(BASE.parent))
    env.setdefault('CODEX_GUARD_PYTHON',sys.executable)
    env.setdefault('CODEX_GUARD_MD_HOME',str(BASE.parent/'md-governance'))
    p=subprocess.run([NODE,str(BASE/'scan.mjs')],input=json.dumps({'root':str(root),'previous':previous,'delegatedRoots':list(delegated_roots)}),text=True,capture_output=True,timeout=90,env=env)
    if p.returncode: raise RuntimeError(p.stderr[-3000:])
    result=json.loads(p.stdout)
    validate_scan(root,result,delegated_roots)
    return result

def expected_sources(root,delegated_roots):
    ignored={'.git','node_modules','__pycache__','.venv','venv','state'}
    extensions=set('js cjs mjs jsx ts cts mts tsx py vue svelte go rs java kt swift c cc cpp h cs rb php sh bash zsh sql wxml wxss css scss html'.split())
    delegated={str(pathlib.Path(p).resolve()) for p in delegated_roots}
    expected=set()
    def walk(directory):
        for item in directory.iterdir():
            if item.name in ignored: continue
            if item.is_symlink(): expected.add(str(item.relative_to(root)))
            elif item.is_dir():
                if (item/'.git').exists() and str(item.resolve()) in delegated: continue
                walk(item)
            elif item.suffix.lstrip('.').lower() in extensions:
                expected.add(str(item.relative_to(root)))
    walk(root)
    return expected

def validate_scan(root,result,delegated_roots):
    if not isinstance(result,dict): raise RuntimeError('Invalid scanner result: expected file map')
    for name,row in result.items():
        if not isinstance(row,dict) or not re.fullmatch('[0-9a-f]{64}',str(row.get('hash',''))) or not isinstance(row.get('metrics'),dict):
            raise RuntimeError('Invalid scanner result for '+name)
        for metric in row['metrics'].values():
            if not isinstance(metric,dict) or not all(key in metric for key in ('value','count','line','message')):
                raise RuntimeError('Invalid scanner diagnostic for '+name)
    missing=expected_sources(root,delegated_roots)-set(result)
    if missing: raise RuntimeError('Incomplete scan coverage: '+', '.join(sorted(missing)[:10]))

def coverage_outcome(current,kind):
    if any(not name.startswith('@md:') for name in current): return {}
    message='Local code guard: no source files covered; code verification not performed. Instruction checks do not certify source code. This is not a passing code verification.'
    if kind in ('Stop','SubagentStop'): return {'systemMessage':message}
    return {'hookSpecificOutput':{'hookEventName':kind,'additionalContext':message}}

def registered_roots(prefix):
    return [json.loads(p.read_text())['root'] for p in STATE.glob(prefix+'-*.json')]
def root_for(event):
    cwd=pathlib.Path(event.get('cwd') or os.getcwd()).resolve()
    tool=event.get('tool_input') or {}
    if isinstance(tool,dict) and tool.get('workdir'): cwd=pathlib.Path(tool['workdir']).resolve()
    p=subprocess.run(['git','-C',str(cwd),'rev-parse','--show-toplevel'],text=True,capture_output=True)
    return pathlib.Path(p.stdout.strip()).resolve() if p.returncode==0 else cwd

def failures(current,baseline,owned=None):
    errors=[]
    for file,row in current.items():
        if owned is not None and file not in owned: continue
        old=baseline.get(file,{})
        forced=[m for k,m in row['metrics'].items() if k.startswith('md:managed-')]
        if forced:
            errors.extend('%s:%s %s'%(file,m['line'],m['message']) for m in forced)
            continue
        if row['hash']==old.get('hash') and row['metrics']==old.get('metrics'): continue
        for key,m in row['metrics'].items():
            if key=='md:review-required' and row['hash']==old.get('hash'): continue
            before=old.get('metrics',{}).get(key,{})
            hard=key.startswith(('parse:','guard:unsupported','guard:symlink')) or key=='parse' or key=='md:review-required'
            if hard or m['value']>before.get('value',0) or m['count']>before.get('count',0):
                errors.append('%s:%s %s'%(file,m['line'],m['message']))
    return errors

def failure_outcome(kind,errors,current,data,event=None):
    event=event or {}
    reason='Local code guard FAILED. Fix these errors; do not raise limits, add suppressions or reset the baseline.\n'+'\n'.join(errors[:25])
    if kind not in ('Stop','SubagentStop'):
        return {'hookSpecificOutput':{'hookEventName':kind,'additionalContext':reason}}
    fingerprint=hashlib.sha256(json.dumps({'errors':errors,'hashes':{k:v['hash'] for k,v in current.items()}},sort_keys=True).encode()).hexdigest()
    scope=[event.get('turn_id'),event.get('agent_id')]
    if event.get('stop_hook_active') or (data.get('last_stop_scope')==scope and data.get('last_stop_failure')==fingerprint):
        message=reason+'\nUnresolved failure already reported; stopping retries. This is not a passing verification.'
        return {'continue':False,'stopReason':message,'systemMessage':message}
    data['last_stop_failure']=fingerprint
    data['last_stop_scope']=scope
    return {'decision':'block','reason':reason}

def save_json(path,data):
    fd,name=tempfile.mkstemp(prefix='.guard-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            json.dump(data,stream); stream.flush(); os.fsync(stream.fileno())
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)

def unavailable_path(event):
    identity=[event.get('session_id'),event.get('cwd'),event.get('agent_id')]
    key=hashlib.sha256(json.dumps(identity).encode()).hexdigest()
    return STATE/(key+'.unavailable')

def unavailable(event,error):
    kind=event.get('hook_event_name','Stop')
    diagnostic='Local code guard unavailable: '+str(error)
    data={}
    try:
        STATE.mkdir(mode=0o700,exist_ok=True)
        path=unavailable_path(event)
        if path.exists(): data=json.loads(path.read_text())
        result=failure_outcome(kind,[diagnostic],{},data,event)
        save_json(path,data)
        return result
    except Exception:
        if kind in ('Stop','SubagentStop'):
            return {'continue':False,'stopReason':diagnostic,'systemMessage':diagnostic+'; recovery state unavailable. Verification did not pass.'}
        return {'hookSpecificOutput':{'hookEventName':kind,'additionalContext':diagnostic}}

def dispatch(event):
    try:
        verify_integrity()
        outcome=main(event)
        path=unavailable_path(event)
        if path.exists(): path.unlink()
        return outcome
    except Exception as error:
        return unavailable(event,error)

def scoped_errors(current,baseline,data,pending,final_root=None):
    owned=set(data.get('owned',[]))
    task_base=data.get('task_baseline',baseline)
    errors=failures(current,baseline) if data.get('history_audit') else failures(current,task_base,owned)
    outstanding={name for name in owned if name in current and failures({name:current[name]},task_base)}
    return errors,sorted(outstanding)

def signatures(current):
    return {name:hashlib.sha256(json.dumps(row,sort_keys=True).encode()).hexdigest() for name,row in current.items()}

def observe_tool(data,current,kind,event=None):
    observed=signatures(current)
    owned=set(data.get('owned',[]))
    if 'inflight' in data:
        owned.update(name for name,value in observed.items() if value!=data['inflight'].get(name))
    data['owned']=sorted(owned)
    data['scope_version']=2
    if kind=='PreToolUse':
        task_base=data.setdefault('task_baseline',dict(data['baseline']))
        for name,row in current.items():
            if name not in owned: task_base[name]=row
        for name in set(task_base)-set(current)-owned: task_base.pop(name,None)
        data['inflight']=observed
    elif kind=='PostToolUse' and tool_still_running(event or {}): data['inflight']=observed
    else: data.pop('inflight',None)

def tool_still_running(event):
    response=event.get('tool_response',{})
    if isinstance(response,dict) and response.get('session_id') is not None: return True
    return 'Script running with cell ID' in str(response) or 'Process running with session ID' in str(response)

def read_pending(path):
    value=json.loads(path.read_text()) if path.exists() else []
    if isinstance(value,list):
        return {'version':2,'files':[],'legacy_unattributed':value}
    return value

def inherited_outcome(kind,errors,data):
    message='Local code guard: %d pre-existing diagnostics outside this task. Baseline preserved; this is not certification of the inherited source.\n'%len(errors)+'\n'.join(errors[:3])
    if kind in ('Stop','SubagentStop'): return {'systemMessage':message}
    if data.get('inherited_reported'): return {}
    data['inherited_reported']=True
    return {'hookSpecificOutput':{'hookEventName':kind,'additionalContext':message}}

def stop_roots(event,prefix):
    if STATE.exists() and not STATE.is_dir(): raise RuntimeError('Guard state is not a directory; cannot certify this turn.')
    if unavailable_path(event).exists() and not list(STATE.glob(prefix+'-*.json')):
        return main(dict(event,_single_root=True))
    messages=[]
    halt=False
    final_root=str(root_for(event))
    saved_roots=list(STATE.glob(prefix+'-*.json'))
    if not saved_roots:
        return {'systemMessage':'Local code guard: no registered roots; verification not performed.'}
    for saved in saved_roots:
        data=json.loads(saved.read_text())
        outcome=main(dict(event,cwd=data['root'],tool_input={},_single_root=True,_final_root=final_root))
        if outcome.get('decision')=='block': return outcome
        if outcome.get('systemMessage'): messages.append(outcome['systemMessage'])
        halt=halt or outcome.get('continue') is False
    if not messages: return {}
    result={'systemMessage':'\n'.join(messages)}
    if halt: result.update({'continue':False,'stopReason':'\n'.join(messages)})
    return result

def main(event):
    kind=event.get('hook_event_name','Stop')
    sid=str(event.get('session_id','manual'))
    prefix=hashlib.sha256(sid.encode()).hexdigest()[:20]
    if kind in ('Stop','SubagentStop') and not event.get('_single_root'):
        return stop_roots(event,prefix)
    root=root_for(event)
    STATE.mkdir(mode=0o700,exist_ok=True)
    os.chmod(STATE,0o700)
    sid=str(event.get('session_id','manual'))
    key=prefix+'-'+hashlib.sha256(str(root).encode()).hexdigest()
    statefile=STATE/(key+'.json')
    rootkey=hashlib.sha256(str(root).encode()).hexdigest()
    baselinefile=STATE/('baseline-'+rootkey+'.json')
    pendingfile=STATE/('pending-'+rootkey+'.json')
    with (STATE/('root-'+rootkey+'.lock')).open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        if statefile.exists(): data=json.loads(statefile.read_text())
        else:
            if kind not in ('SessionStart','PreToolUse'):
                raise RuntimeError('Missing pre-edit baseline. Cannot certify this turn; initialize before the next edit, preserving current changes for review.')
            snapshot=run_scan(root,{},registered_roots(prefix))
            baseline=json.loads(baselinefile.read_text()) if baselinefile.exists() else snapshot
            if not baselinefile.exists():
                save_json(baselinefile,baseline)
            data={'root':str(root),'baseline':baseline,'latest':snapshot,'task_baseline':snapshot,'initial_hashes':{name:row['hash'] for name,row in snapshot.items()}}
            save_json(statefile,data)
        if kind=='PreToolUse':
            current=run_scan(root,data['latest'],registered_roots(prefix))
            observe_tool(data,current,kind,event)
            data['latest']=current
            save_json(statefile,data)
        if kind in ('SessionStart','PreToolUse'):
            if kind=='SessionStart':
                return {'hookSpecificOutput':{'hookEventName':kind,'additionalContext':'Global local-code-guard active: read ~/.codex/skills/local-code-guard/SKILL.md before coding. Code and persistent instruction edits are scanned synchronously and finalization is gated; read ~/.codex/skills/instruction-maintenance/SKILL.md before changing instruction documents. Unsupported languages require a verified adapter.'}}
            return {}
        data['history_audit']=os.environ.get('CODEX_GUARD_SCOPE')=='history'
        data['baseline']=json.loads(baselinefile.read_text())
        if 'initial_hashes' not in data:
            data['initial_hashes']={name:row['hash'] for name,row in data['latest'].items()}
        current=run_scan(root,data['latest'],registered_roots(prefix))
        errors=failures(current,data['baseline'])
        pending=read_pending(pendingfile)
        observe_tool(data,current,kind,event)
        task_errors,outstanding=scoped_errors(current,data['baseline'],data,pending,event.get('_final_root'))
        data['owned']=[name for name in data.get('owned',[]) if name in outstanding]
        pending['files']=outstanding
        save_json(pendingfile,pending)
        data['latest']=current
        save_json(statefile,data)
        if errors:
            outcome=failure_outcome(kind,task_errors,current,data,event) if task_errors else inherited_outcome(kind,errors,data)
            save_json(statefile,data)
            return outcome
        data.pop('last_stop_failure',None)
        save_json(baselinefile,current)
        data['baseline']=current
        save_json(statefile,data)
        return coverage_outcome(current,kind)
if __name__=='__main__':
    try:
        event=json.load(sys.stdin)
        print(json.dumps(dispatch(event)))
    except Exception as e:
        print(json.dumps({'continue':False,'stopReason':str(e),'systemMessage':'Local code guard input unavailable; verification did not pass: '+str(e)}))
