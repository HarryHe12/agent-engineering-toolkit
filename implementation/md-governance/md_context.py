"""Versioned inputs for one narrowly scoped independent instruction review."""
from pathlib import Path
from md_rules import digest, added_units, units, lint, similar_clauses
from md_gate import discover,linked_documents
import md_store


def root_for(target):
    candidates=[p for p in target.parents if (p/'.git').exists() or p.name=='.codex']
    return candidates[0] if candidates else target.parent


def document(identity,path,text=None):
    path=Path(path).resolve()
    content=path.read_text() if text is None else text
    return {'id':identity,'path':str(path),'exists':path.exists(),'sha256':digest(content),'text':content}


def build(target,draft,request,evidence=()):
    if Path(target).is_symlink(): raise ValueError('Authority must not be a symlink.')
    target=Path(target).resolve(); draft=Path(draft).resolve()
    if target==draft: raise ValueError('Candidate must be a separate file and authority must not be a symlink.')
    old=target.read_text() if target.exists() else ''
    approved=md_store.read_json(md_store.STATE/'managed.json',{}).get(str(target))
    if approved and digest(old)!=approved:
        raise ValueError('Authority differs from its approved version; preserve current work and restore the approved base before proposing a candidate.')
    new=draft.read_text()
    root=root_for(target)
    known={p.resolve() for p in discover(root)}
    queue=list(linked_documents(target,root,new))
    while queue:
        path=queue.pop().resolve()
        if path in known: continue
        known.add(path); queue.extend(linked_documents(path,root))
    paths=sorted(p for p in known if p!=target)
    docs=[document('base',target,old),document('candidate',draft,new),document('request',request)]
    if not docs[-1]['text'].strip(): raise ValueError('A concrete request/source is required for independent review.')
    docs.extend(document('authority-'+str(i),p) for i,p in enumerate(paths))
    docs.extend(document('evidence-'+str(i),p) for i,p in enumerate(evidence))
    corpus={row['path']:row['text'] for row in docs if row['id'].startswith('authority-')}
    errors=lint(new,target,corpus)
    packet={'target':str(target),'draft':str(draft),'request':str(Path(request).resolve()),
            'evidence':[str(Path(p).resolve()) for p in evidence], 'documents':docs,
            'added':added_units(old,new),'removed':added_units(new,old),
            'structural_errors':errors,'similar_clauses':similar_clauses(new,corpus,target)}
    return old,new,packet
