"""Review, actionable feedback and version-bound approval for publication."""
import json
import uuid
from pathlib import Path
import md_backend
import md_context
import md_seal
from md_rules import digest
from md_store import atomic_text
from md_verdict import validate,POLICY


def fingerprint(packet):
    return digest(md_seal.canonical(packet))


def quality_versions():
    return {p.name:digest(p.read_text()) for p in sorted(Path(__file__).parent.glob('md_*.py'))}

def run(target,draft,request,evidence=()):
    old,new,packet=md_context.build(target,draft,request,evidence)
    if packet['structural_errors']:
        return {'decision':'revise','stage':'structure','errors':packet['structural_errors'],'published':False,
                'next_action':'Merge the identified repeats, correct links, or shorten/move content within existing budgets; rerun analyze.'}
    if old==new: raise ValueError('No candidate change; cannot mint independent approval for an already written instruction.')
    versions=quality_versions(); policy_version=digest(POLICY.read_text())
    run_id=uuid.uuid4().hex
    destination=md_seal.run_directory(run_id)
    destination.mkdir(mode=0o700,parents=True)
    atomic_text(destination/'input.json',json.dumps(packet,ensure_ascii=False,indent=2)+'\n')
    try:
        verdict,execution=md_backend.invoke(packet,destination)
        if versions!=quality_versions() or policy_version!=digest(POLICY.read_text()):
            raise ValueError('Quality checker or criteria changed during review; rerun against current versions.')
        accepted=validate(verdict,packet)
        _,_,current=md_context.build(target,draft,request,evidence)
        if fingerprint(current)!=fingerprint(packet): raise ValueError('Review inputs changed while reviewer was running; retry against current versions.')
        payload={'run_id':run_id,'input_sha256':fingerprint(packet),'packet':packet,
                 'policy_sha256':policy_version,'quality_sha256':versions,
                 'verdict':verdict,'execution':execution}
        atomic_text(destination/'attestation.json',json.dumps(md_seal.signed(payload),ensure_ascii=False,indent=2)+'\n')
        token={'independent_review':run_id}
        atomic_text(destination/'review.json',json.dumps(token)+'\n')
        feedback={'decision':'pass' if accepted else 'revise','published':False,'review':str(destination/'review.json'),
                  'run_id':run_id,'verdict':verdict,'execution':execution}
    except Exception as error:
        feedback={'decision':'unavailable','published':False,'run_id':run_id,'error':str(error),
                  'next_action':'Keep the authority unchanged. Correct inputs or reviewer availability, then rerun review.'}
    atomic_text(destination/'feedback.json',json.dumps(feedback,ensure_ascii=False,indent=2)+'\n')
    return feedback


def require(review,target,old,new):
    run_id=review.get('independent_review','')
    if not run_id: raise ValueError('A separate independent review is required; author-authored review JSON is not approval.')
    directory=md_seal.run_directory(run_id)
    path=directory/'attestation.json'
    if not path.exists(): raise ValueError('Missing independent reviewer attestation.')
    record=md_seal.verified(json.loads(path.read_text()))
    if record['run_id']!=run_id: raise ValueError('Independent review run mismatch.')
    packet=record['packet']
    if packet['target']!=str(Path(target).resolve()): raise ValueError('Independent review target mismatch.')
    if packet['documents'][0]['sha256']!=digest(old) or packet['documents'][1]['sha256']!=digest(new):
        raise ValueError('Stale independent review: original or candidate changed.')
    _,_,current=md_context.build(target,Path(packet['draft']),Path(packet['request']),packet['evidence'])
    if fingerprint(current)!=record['input_sha256'] or digest(POLICY.read_text())!=record['policy_sha256']:
        raise ValueError('Stale independent review: context, evidence or quality criteria changed.')
    if record.get('quality_sha256')!=quality_versions():
        raise ValueError('Stale independent review: quality checker implementation changed.')
    if not validate(record['verdict'],packet): raise ValueError('Independent review requires revision; read feedback.json.')
    return record


def verdict_passed(verdict,packet):
    judgments=list(verdict['dimensions'].values())+verdict['clauses']
    covered={item['id'] for item in verdict['clauses']}=={item['id'] for item in packet['added']}
    return verdict['decision']=='pass' and bool(verdict['dimensions']) and covered and all(item['status']=='pass' for item in judgments)


def published(record):
    """A receipt must trace to a sealed passing run, not any signed JSON."""
    try:
        directory=md_seal.run_directory(record['run_id'])
        attestation=md_seal.verified(json.loads((directory/'attestation.json').read_text()))
        packet=attestation['packet']; execution=attestation['execution']
        bound=(record['input_sha256']==attestation['input_sha256'] and record['target']==packet['target'] and
               record['candidate_sha256']==packet['documents'][1]['sha256'])
        native=execution.get('provider')=='native Codex CLI' and execution.get('returncode')==0 and execution.get('tools_used') is False
        return bound and native and verdict_passed(attestation['verdict'],packet)
    except (ValueError,KeyError,OSError,TypeError): return False
