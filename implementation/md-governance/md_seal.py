"""Local attestations: author JSON alone is never a review credential."""
import hashlib
import hmac
import json
import os
import secrets
from pathlib import Path
import md_store


def canonical(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))


def key():
    state=md_store.STATE
    state.mkdir(mode=0o700,parents=True,exist_ok=True)
    path=state/'review.key'
    if not path.exists():
        try:
            fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
            with os.fdopen(fd,'wb') as stream: stream.write(secrets.token_bytes(32))
        except FileExistsError: pass
    value=path.read_bytes()
    if len(value)!=32: raise ValueError('Independent review signing key is invalid.')
    return value


def sign(value):
    return hmac.new(key(),canonical(value).encode(),hashlib.sha256).hexdigest()


def signed(value):
    return {'payload':value,'signature':sign(value)}


def verified(envelope):
    if not isinstance(envelope,dict): raise ValueError('Missing independent review attestation.')
    value=envelope.get('payload')
    signature=envelope.get('signature','')
    if not isinstance(value,dict) or not hmac.compare_digest(str(signature),sign(value)):
        raise ValueError('Invalid independent review attestation.')
    return value


def run_directory(run_id):
    if len(run_id)!=32 or any(c not in '0123456789abcdef' for c in run_id):
        raise ValueError('Invalid independent review run ID.')
    return md_store.STATE/'reviews'/run_id
