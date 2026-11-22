"""Deterministic checks for active agent instructions; no model/API calls."""
import hashlib,re,unicodedata
from pathlib import Path
from urllib.parse import unquote
LIMITS={'agents.md':3000,'skill.md':5000}
EXCLUDED={'archive','archives','node_modules','.git','.venv','venv','__pycache__','state','work','outputs'}
def digest(text):
    return hashlib.sha256(text.encode()).hexdigest()
def normalize(text):
    text=unicodedata.normalize('NFKC',text).casefold()
    text=re.sub(r'^\s*(?:[-*+] |\d+[.)] )','',text)
    return ''.join(c for c in text if c.isalnum())
def visible_lines(text):
    fenced=False; front=text.startswith('---\n'); lines=[]
    for index,line in enumerate(text.splitlines(),1):
        if front:
            if index>1 and line.strip()=='---': front=False
            continue
        if re.match(r'^\s*(```|~~~)',line): fenced=not fenced; continue
        if not fenced: lines.append((index,line))
    return lines
def units(text):
    result=[]; current=[]; start=1
    for index,line in visible_lines(text)+[(0,'')]:
        boundary=not line.strip() or line.startswith('#') or re.match(r'^\s*(?:[-*+] |\d+[.)] )',line)
        if boundary and current:
            value=' '.join(current).strip(); result.append({'line':start,'text':value,'id':digest(normalize(value))}); current=[]
        if line.strip() and not line.startswith('#'):
            if not current: start=index
            current.append(line.strip())
    return result
def is_active(path,root):
    try: parts=path.relative_to(root).parts
    except ValueError: return False
    if any(p.casefold() in EXCLUDED for p in parts[:-1]): return False
    name=path.name.casefold()
    return name in {'agents.md','skill.md','requirements.md','design.md','tasks.md','quality_gates.md','workflow.md','knowledge.md'} or name.startswith('spec') and name.endswith('.md') or 'specs' in parts[:-1] or 'rules' in parts[:-1]
def issue(key,message,line=1,value=1):
    return key,{'value':value,'count':1,'line':line,'message':message}
def heading_errors(text):
    seen=set(); stack=[]; errors={}
    for line,value in visible_lines(text):
        m=re.match(r'^(#{1,6})\s+(.+)',value)
        if not m: continue
        level=len(m[1]); stack=[s for s in stack if s[0]<level]
        key=tuple(s[1] for s in stack)+(normalize(m[2]),)
        if key in seen: errors.update([issue('md:duplicate-heading:'+digest(str(key)), 'Duplicate heading in the same section.',line)])
        seen.add(key); stack.append((level,normalize(m[2])))
    return errors
def link_errors(text,target):
    errors={}
    for line,value in visible_lines(text):
        for raw in re.findall(r'\]\(([^)]+)\)',value):
            dest=raw.strip().split(' "')[0].strip('<>')
            if not dest or dest.startswith(('#','http:','https:','mailto:','plugin:','app:','codex:')): continue
            dest=unquote(dest.split('#')[0]); dest=re.sub(r':\d+$','',dest)
            linked=Path(dest) if dest.startswith('/') else target.parent/dest
            if not linked.exists(): errors.update([issue('md:broken-link:'+dest,'Missing local link target: '+dest,line)])
    return errors
def clause_owners(corpus):
    owners={}
    for source,content in corpus.items():
        canonical=str(Path(source).resolve())
        for row in units(content):
            key=normalize(row['text'])
            if len(key)>=18: owners.setdefault(key,set()).add(canonical)
    return owners
def sentence_duplicates(text):
    errors={}
    for row in units(text):
        seen=set()
        sentences=re.split(r'(?<=[。！？!?])\s*|(?<=\.)(?:\s+|$)',row['text'])
        for sentence in sentences:
            key=normalize(sentence)
            if len(key)<8: continue
            if key in seen:
                errors.update([issue('md:duplicate-sentence:'+digest(key),'Repeated sentence in the same instruction clause: '+sentence.strip(),row['line'])])
            seen.add(key)
    return errors

def lint(text,target,corpus=None,index=None):
    target=Path(target); out={}; cap=LIMITS.get(target.name.casefold(),10000)
    if len(text)>cap: out.update([issue('md:size','Instruction character budget exceeded: %s > %s.'%(len(text),cap),value=len(text))])
    entries=units(text); seen={}
    for row in entries:
        key=normalize(row['text'])
        if len(row['text'])>260: out.update([issue('md:long-clause:'+row['id'],'Instruction clause exceeds 260 characters; separate distinct decisions.',row['line'],len(row['text']))])
        if len(key)<18: continue
        if key in seen: out.update([issue('md:duplicate:'+row['id'],'Repeated instruction clause.',row['line'])])
        seen[key]=row
    owners=index if index is not None else clause_owners(corpus or {})
    for key,row in seen.items():
        elsewhere=owners.get(key,set())-{str(target.resolve())}
        if elsewhere: out.update([issue('md:cross-duplicate:'+row['id'],'Instruction already exists in '+sorted(elsewhere)[0],row['line'])])
    out.update(sentence_duplicates(text))
    out.update(heading_errors(text)); out.update(link_errors(text,target))
    if re.search(r'^(?:<{7}|={7}|>{7})',text,re.M): out.update([issue('md:merge-conflict','Unresolved merge conflict markers.')])
    return out
def added_units(old,new):
    existing={u['id'] for u in units(old)}
    return [u for u in units(new) if u['id'] not in existing]

def similar_clauses(text,corpus,target):
    from difflib import SequenceMatcher
    result=[]
    for candidate in units(text):
        left=normalize(candidate['text'])
        if len(left)<18: continue
        matches=[]
        for source,content in corpus.items():
            if Path(source).resolve()==Path(target).resolve(): continue
            for old in units(content):
                right=normalize(old['text'])
                if not right or min(len(left),len(right))/max(len(left),len(right))<0.7: continue
                ratio=SequenceMatcher(None,left,right).ratio()
                if 0.82<=ratio<1: matches.append({'source':str(source),'text':old['text'],'similarity':round(ratio,3)})
        if matches: result.append({'id':candidate['id'],'matches':sorted(matches,key=lambda x:-x['similarity'])[:3]})
    return result
