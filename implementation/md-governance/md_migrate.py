"""One-time maintenance snapshot of exact pre-existing receipts, never resnapshot."""
import json
import re
import md_store
import md_seal
from md_rules import digest


def snapshot():
    catalog=md_store.STATE/'legacy-receipts.json'
    if catalog.exists():
        old=md_seal.verified(json.loads(catalog.read_text()))
        return {'status':'existing snapshot preserved','receipts':len(old)}
    legacy={}
    for path in (md_store.STATE/'receipts').glob('*.json'):
        row=json.loads(path.read_text())
        if 'payload' in row: continue
        if not isinstance(row.get('target'),str) or not re.fullmatch('[0-9a-f]{64}',str(row.get('candidate_sha256',''))):
            raise ValueError('Invalid historical receipt: '+path.name)
        legacy[path.name]=digest(path.read_text())
    md_store.atomic_text(catalog,json.dumps(md_seal.signed(legacy),indent=2)+'\n')
    return {'status':'one-time exact snapshot created','receipts':len(legacy)}


if __name__=='__main__':
    print(json.dumps(snapshot()))
