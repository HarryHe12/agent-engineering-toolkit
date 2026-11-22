"""Transport stubs for isolated tests; never installed as reviewer backends."""
import json
import md_store
from unittest.mock import patch
import md_context
import md_semantic
from md_verdict import policy


def verdict(packet,status='pass'):
    quote=packet['documents'][1]['text'].strip() or packet['documents'][0]['text'].strip()
    source='candidate' if packet['documents'][1]['text'].strip() else 'base'
    citation=[{'document':source,'quote':quote}]
    dimensions={name:{'status':status,'reason':'Synthetic transport fixture for '+name+'; not evidence of semantic quality.',
                      'suggestion':'' if status=='pass' else 'Revise the affected requirement according to the source contract.',
                      'evidence':citation} for name in policy()['criteria']}
    clauses=[dict(dimensions['basis'],id=row['id']) for row in packet['added']]
    return {'decision':'pass' if status=='pass' else 'revise','dimensions':dimensions,'clauses':clauses}


def run_review(target,draft,request,response=None):
    state=md_store.STATE.resolve()
    if state==(md_store.BASE/'state').resolve() or not target.resolve().is_relative_to(state.parent):
        raise RuntimeError('Test transport refuses installed state or non-fixture authorities; use the real independent reviewer.')
    def backend(packet,destination):
        return response or verdict(packet),{'provider':'native Codex CLI','model':'unit-test transport double','tools_used':False,'returncode':0}
    with patch('md_backend.invoke',side_effect=backend):
        return md_semantic.run(target,draft,request)


def token(target,draft,request):
    result=run_review(target,draft,request)
    if result['decision']!='pass': raise ValueError(str(result))
    return json.loads(__import__('pathlib').Path(result['review']).read_text())
