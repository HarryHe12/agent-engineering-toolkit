import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { Linter } from 'eslint';
import tsParser from '@typescript-eslint/parser';
const linter = new Linter({cwd: path.parse(process.cwd()).root});
const pythonInterpreter = process.env.CODEX_GUARD_PYTHON || 'python3';
const markdownHome = process.env.CODEX_GUARD_MD_HOME || path.resolve(import.meta.dirname,'../md-governance');
const policies = JSON.parse(fs.readFileSync(new URL('./policies.json', import.meta.url),'utf8'));
let retired = [];
const retiredPlugin = {rules: {'no-retired-module': {
  meta: {type:'problem',schema:[],messages:{retired:'Retired module {{old}}. Use {{replacement}}.'}},
  create(context) {
    function check(node,value) {
      if (typeof value !== 'string') return;
      const resolved = value.startsWith('.') ? path.resolve(path.dirname(context.filename),value).replace(/\.(?:[cm]?js|[cm]?ts|tsx|jsx)$/,'') : value;
      for (const item of retired) {
        if (resolved === item.resolved) context.report({node,messageId:'retired',data:{old:value,replacement:item.replacement}});
      }
    }
    return {ImportDeclaration:n=>check(n,n.source.value),ImportExpression:n=>check(n,n.source?.value),
      CallExpression:n=>{if(n.callee.type==='Identifier' && n.callee.name==='require') check(n,n.arguments[0]?.value);}};
  }
}}};
const rules = {
  'max-lines': ['error', { max: 500, skipBlankLines: true, skipComments: true }],
  'max-lines-per-function': ['error', { max: 80, skipBlankLines: true, skipComments: true, IIFEs: true }],
  'max-statements': ['error', 50], complexity: ['error', 15], 'max-depth': ['error', 4],
  'no-restricted-modules': ['error', {paths:[{name:'sys',message:'Deprecated Node module; use node:util.'},{name:'node:sys',message:'Deprecated Node module; use node:util.'}]}],
  'no-restricted-imports': ['error', {paths:[{name:'sys',message:'Deprecated Node module; use node:util.'},{name:'node:sys',message:'Deprecated Node module; use node:util.'}]}],
  'no-restricted-properties': ['error',
    { object: 'fs', property: 'exists', message: 'Use existsSync or an explicit async access check.' },
    { object: 'util', property: 'isArray', message: 'Deprecated; use Array.isArray.' }],
  'no-restricted-syntax': ['error',
    { selector: 'NewExpression[callee.name="Buffer"]', message: 'Deprecated Buffer constructor; use Buffer.from or Buffer.alloc.' }],
};
const supported = /\.(?:[cm]?js|jsx|[cm]?ts|tsx|py)$/i;
const otherCode = /\.(?:vue|svelte|go|rs|java|kt|swift|c|cc|cpp|h|cs|rb|php|sh|bash|zsh|sql|wxml|wxss|css|scss|html)$/i;
const ignored = new Set(['.git', 'node_modules', '__pycache__', '.venv', 'venv', 'state']);
function files(root, delegatedRoots = []) {
  const delegated = new Set(delegatedRoots);
  const out = [];
  function walk(dir) {
    if (dir !== root && fs.existsSync(path.join(dir,'.git')) && delegated.has(fs.realpathSync(dir))) return;
    for (const item of fs.readdirSync(dir, {withFileTypes: true})) {
      if (ignored.has(item.name)) continue;
      if (item.isSymbolicLink()) { out.push(path.join(dir,item.name)); continue; }
      const p = path.join(dir, item.name);
      if (item.isDirectory()) walk(p);
      else if (supported.test(p) || otherCode.test(p)) out.push(p);
    }
  }
  walk(root); return out;
}
function inferredName(node,parent,fallback) {
  return node.id?.name || parent?.key?.name || parent?.key?.value || parent?.id?.name || fallback;
}
function entities(source) {
  const nodes = [];
  const parsed = tsParser.parseForESLint(source, {comment:true,loc:true,range:true,ecmaVersion:'latest',sourceType:'module',ecmaFeatures:{jsx:true}});
  function walk(node, parent, scope) {
    if (!node?.type) return;
    let next = scope;
    if (node.type === 'ClassDeclaration') next = `${scope}/${inferredName(node,parent,'anonymous-class')}`;
    if (/Function/.test(node.type) || node.type === 'ArrowFunctionExpression') {
      const name = inferredName(node,parent,`anonymous-${nodes.filter(n=>n.scope===scope).length}`);
      next = `${scope}/${name}`;
      nodes.push({start:node.loc.start.line,end:node.loc.end.line,name:next,scope});
    }
    for (const key of parsed.visitorKeys[node.type] || []) {
      const children = Array.isArray(node[key]) ? node[key] : [node[key]];
      for (const child of children) walk(child,node,next);
    }
  }
  walk(parsed.ast,null,'');
  nodes.comments = parsed.ast.comments || [];
  return nodes;
}
function recordDiagnostic(out,m,nodes) {
    const metric = ['max-lines','max-lines-per-function','complexity','max-depth','max-statements'].includes(m.ruleId);
    const key = `${m.ruleId || 'parse'}:${m.ruleId === 'max-lines' ? 'file' : (nodes.filter(n=>n.start<=m.line && n.end>=m.line).sort((a,b)=>(a.end-a.start)-(b.end-b.start))[0]?.name || 'top-level')}:${metric ? '' : m.message}`;
    const value = metric ? Number(m.message.match(/(?:\(|complexity of |depth of )(\d+)/)?.[1] || 1) : 1;
    if (!out[key]) out[key] = {value:0, count:0, message:m.message, line:m.line};
    out[key].value = Math.max(out[key].value, value); out[key].count++;
}
function jsMetrics(source, file) {
  const messages = linter.verify(source, [{ files: ['**/*.{js,cjs,mjs,jsx,ts,tsx,cts,mts}'], languageOptions: {
    parser: tsParser, ecmaVersion: 'latest', sourceType: 'module',
    parserOptions: { ecmaFeatures: {jsx: true} },
  }, plugins: {local:retiredPlugin}, linterOptions: {noInlineConfig: true}, rules: {...rules,'local/no-retired-module':'error'} }], {filename: file});
  const out = {};
  let nodes = [];
  try { nodes = entities(source); } catch {}
  for (const m of messages) recordDiagnostic(out,m,nodes);
  for (const comment of nodes.comments || []) {
    if (!/(?:\beslint-(?:disable|enable|env)\b|^\s*eslint\s)/.test(comment.value)) continue;
    const key = 'guard:inline-override';
    out[key] = {value:(out[key]?.value || 0)+1,count:1,message:'Inline ESLint override is forbidden.',line:comment.loc.start.line};
  }
  return out;
}
const request = JSON.parse(fs.readFileSync(0,'utf8'));
retired = policies.retiredModules.filter(item=>path.resolve(item.root) === path.resolve(request.policyRoot || request.root)).map(item=>({
  ...item, resolved: item.module.startsWith('.') ? path.resolve(request.root,item.module).replace(/\.(?:[cm]?js|[cm]?ts|tsx|jsx)$/,'') : item.module
}));
const previous = request.previous || {};
const result = {};
for (const file of files(request.root,request.delegatedRoots)) {
  const relative = path.relative(request.root,file);
  if (fs.lstatSync(file).isSymbolicLink()) {
    result[relative] = {hash:crypto.createHash('sha256').update(fs.readlinkSync(file)).digest('hex'),metrics:{'guard:symlink':{value:1,count:1,line:1,message:'Changed symlink is not certified; inspect the target and register its root.'}}};
    continue;
  }
  const source = fs.readFileSync(file,'utf8');
  const hash = crypto.createHash('sha256').update(source).digest('hex');
  if (previous[relative]?.hash === hash) { result[relative] = previous[relative]; continue; }
  let metrics;
  if (/\.(?:[cm]?js|jsx|[cm]?ts|tsx)$/i.test(file)) metrics = jsMetrics(source, file);
  else if (/\.py$/i.test(file)) {
    const {spawnSync} = await import('node:child_process');
    const r = spawnSync(pythonInterpreter,[path.join(import.meta.dirname,'python_metrics.py')],{input:source,encoding:'utf8'});
    if (r.status !== 0) throw new Error('Python checker failed: '+r.stderr);
    metrics = JSON.parse(r.stdout);
  } else metrics = {'guard:unsupported': {value:1,count:1,line:1,message:'No checker installed for this language. Add and validate an adapter before claiming completion.'}};
  result[relative] = {hash, metrics};
}
if (!request.sourceOnly) {
  const {spawnSync: scanDocuments} = await import('node:child_process');
  const documentScan = scanDocuments(pythonInterpreter,[path.join(markdownHome,'md_gate.py')], {
    input:JSON.stringify({root:request.root,previous}),encoding:'utf8',maxBuffer:32*1024*1024,
  });
  if (documentScan.status !== 0) throw new Error('Instruction checker failed: '+documentScan.stderr);
  Object.assign(result,JSON.parse(documentScan.stdout));
}
process.stdout.write(JSON.stringify(result));
