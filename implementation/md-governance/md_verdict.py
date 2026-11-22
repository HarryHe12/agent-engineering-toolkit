"""Validate coverage, evidence and actionable feedback from a separate reviewer."""
import json
from pathlib import Path

POLICY=Path(__file__).with_name('review_policy.json')


def policy():
    return json.loads(POLICY.read_text())


def evidence_valid(items,documents):
    if not isinstance(items,list) or not items: raise ValueError('Reviewer must cite supplied evidence.')
    for item in items:
        quote=item.get('quote','')
        if not quote.strip() or quote not in documents.get(item.get('document'), ''):
            raise ValueError('Reviewer cited nonexistent evidence.')


def judgment(row,documents):
    if row.get('status') not in ('pass','revise','needs_evidence'):
        raise ValueError('Invalid reviewer status.')
    if len(row.get('reason','').strip())<12: raise ValueError('Reviewer rationale is not specific.')
    evidence_valid(row.get('evidence'),documents)
    if row['status']!='pass' and len(row.get('suggestion','').strip())<8:
        raise ValueError('Failed review needs actionable revision advice.')


def validate(verdict,packet):
    criteria=policy()['criteria']
    docs={row['id']:row['text'] for row in packet['documents']}
    dimensions=verdict.get('dimensions',{})
    if set(dimensions)!=set(criteria): raise ValueError('Reviewer did not assess every quality criterion.')
    for row in dimensions.values(): judgment(row,docs)
    clauses=verdict.get('clauses',[])
    expected={row['id'] for row in packet['added']}
    if len(clauses)!=len(expected) or {row.get('id') for row in clauses}!=expected:
        raise ValueError('Reviewer did not assess every added clause.')
    for row in clauses: judgment(row,docs)
    passed=all(row['status']=='pass' for row in list(dimensions.values())+clauses)
    if verdict.get('decision')!=('pass' if passed else 'revise'):
        raise ValueError('Reviewer decision contradicts individual criteria.')
    return passed


def schema():
    citation={'type':'object','additionalProperties':False,'required':['document','quote'],
              'properties':{'document':{'type':'string'},'quote':{'type':'string'}}}
    properties={'status':{'type':'string','enum':['pass','revise','needs_evidence']},
                'reason':{'type':'string'},'suggestion':{'type':'string'},
                'evidence':{'type':'array','items':citation}}
    row={'type':'object','additionalProperties':False,'required':list(properties),'properties':properties}
    clause={'type':'object','additionalProperties':False,'required':['id']+list(properties),
            'properties':dict(properties,id={'type':'string'})}
    dimensions={'type':'object','additionalProperties':False,'required':list(policy()['criteria']),
                'properties':{name:row for name in policy()['criteria']}}
    return {'type':'object','additionalProperties':False,'required':['decision','dimensions','clauses'],
            'properties':{'decision':{'type':'string','enum':['pass','revise']},
                          'dimensions':dimensions,'clauses':{'type':'array','items':clause}}}
