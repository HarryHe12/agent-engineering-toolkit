"""Local review receipts bind the exact candidate and prior document versions."""
import json,os,tempfile
from pathlib import Path
from md_rules import digest,added_units
BASE=Path(__file__).resolve().parent
STATE=BASE/'state'
def read_json(path,default):
    return json.loads(path.read_text()) if path.exists() else default

def atomic_text(path,text):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    mode=path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd,name=tempfile.mkstemp(prefix='.md-candidate-',dir=str(path.parent))
    try:
        with os.fdopen(fd,'w') as f: f.write(text); f.flush(); os.fsync(f.fileno())
        os.chmod(name,mode); os.replace(name,path)
    finally:
        if Path(name).exists(): Path(name).unlink()
def receipt_path(target,content):
    key=digest(str(Path(target).resolve()))+'-'+digest(content)
    return STATE/'receipts'/(key+'.json')
def verify_review(review,target,old,new):
    from md_semantic import require
    require(review,target,old,new)
    return True

def approve(target,old,new,review):
    from md_semantic import require
    from md_seal import signed
    record=require(review,target,old,new)
    STATE.mkdir(mode=0o700,exist_ok=True); os.chmod(STATE,0o700)
    receipt={'target':str(Path(target).resolve()),'candidate_sha256':digest(new),
             'review_type':'independent native Codex review; not human approval',
             'run_id':record['run_id'],'input_sha256':record['input_sha256'],
             'verdict':record['verdict'],'execution':record['execution']}
    atomic_text(receipt_path(target,new),json.dumps(signed(receipt),ensure_ascii=False,indent=2)+'\n')
    managed=read_json(STATE/'managed.json',{})
    managed[str(Path(target).resolve())]=digest(new)
    atomic_text(STATE/'managed.json',json.dumps(managed,ensure_ascii=False,indent=2)+'\n')

def has_receipt(target,text):
    from md_seal import verified
    p=receipt_path(target,text)
    if not p.exists(): return False
    envelope=read_json(p,{})
    if 'payload' in envelope:
        try: record=verified(envelope)
        except ValueError: return False
        from md_semantic import published
        return record.get('candidate_sha256')==digest(text) and record.get('target')==str(Path(target).resolve()) and published(record)
    catalog=read_json(STATE/'legacy-receipts.json',{})
    try: legacy=verified(catalog)
    except ValueError: return False
    return legacy.get(p.name)==digest(p.read_text()) and envelope.get('candidate_sha256')==digest(text) and envelope.get('target')==str(Path(target).resolve())
