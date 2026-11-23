"""Scan instruction documents for the global synchronous code hook."""
import json,os,re,sys
from urllib.parse import unquote
from pathlib import Path
from md_rules import digest,is_active,lint,issue,EXCLUDED,link_errors,clause_owners
from md_store import STATE,read_json,has_receipt
GLOBAL=Path(os.environ.get('CODEX_HOME',str(Path(__file__).resolve().parent.parent)))/'AGENTS.md'
def linked_documents(path,root,text=None):
    root=root.resolve()
    result=[]
    content=path.read_text() if text is None else text
    for raw in re.findall(r'\]\(([^)]+)\)',content):
        dest=unquote(raw.strip().split(' "')[0].strip('<>').split('#')[0])
        if not dest.casefold().endswith('.md') or '://' in dest: continue
        linked=(path.parent/dest).resolve()
        owner=root if linked.is_relative_to(root) else GLOBAL.parent.resolve()
        if not linked.is_relative_to(owner): continue
        historical={'devlogs','handoffs','decisions','reviews','versions','releases','planning','checklists','task-tree','tasks','epics'}
        if any(part.casefold() in EXCLUDED|historical for part in linked.relative_to(owner).parts[:-1]): continue
        if linked.name in {'PROJECT_BRIEF.md','CURRENT_STATE.md'}: continue
        if linked.exists() and linked.is_file() and not linked.is_symlink(): result.append(linked)
    return result
def discover(root):
    root=Path(root).resolve()
    result=[]
    if root!=GLOBAL.parent.resolve():
        for directory,dirs,names in os.walk(root,followlinks=False):
            dirs[:]=[d for d in dirs if d.casefold() not in EXCLUDED and not (Path(directory)/d).is_symlink()]
            for name in names:
                p=Path(directory)/name
                if name.casefold().endswith('.md') and not p.is_symlink() and is_active(p,root): result.append(p)
    if GLOBAL.exists() and GLOBAL.resolve() not in result: result.append(GLOBAL.resolve())
    for raw in read_json(STATE/'managed.json',{}):
        p=Path(raw)
        if p.exists() and p not in result and (p.is_relative_to(root) or p==GLOBAL or p.is_relative_to(GLOBAL.parent/'skills')): result.append(p)
    pending=list(result); seen=set(result)
    while pending:
        for linked in linked_documents(pending.pop(),root):
            if linked not in seen: seen.add(linked); result.append(linked); pending.append(linked)
    return result
def scan(root,previous):
    root=Path(root).resolve(); result={}; paths=discover(root)
    corpus={str(p):p.read_text() for p in paths}
    managed=read_json(STATE/'managed.json',{})
    index=clause_owners(corpus)
    for p in paths:
        text=corpus[str(p)]; key='@md:'+str(p.resolve()); old=previous.get(key,{})
        if digest(text)==old.get('hash'): metrics={k:v for k,v in old['metrics'].items() if not k.startswith(('md:review-','md:managed-review-','md:broken-link:'))}
        else: metrics=lint(text,p,corpus,index=index)
        metrics.update(link_errors(text,p))
        approved=has_receipt(p,text)
        if not approved:
            rule='md:managed-review-required' if str(p.resolve()) in managed else 'md:review-required'
            metrics=dict(metrics); metrics.update([issue(rule,'Instruction edit needs a version-bound semantic review and preflight via md_write.py.')])
        result[key]={'hash':digest(text),'metrics':metrics}
    for raw in managed:
        p=Path(raw)
        if not p.exists() and (p.is_relative_to(root) or p==GLOBAL or p.is_relative_to(GLOBAL.parent/'skills')):
            result['@md:'+raw]={'hash':'missing','metrics':dict([issue('md:managed-missing','Managed instruction document was deleted without an approved retirement: '+raw)])}
    return result
def main():
    request=json.load(sys.stdin)
    print(json.dumps(scan(request['root'],request.get('previous',{})),ensure_ascii=False))
if __name__=='__main__': main()
