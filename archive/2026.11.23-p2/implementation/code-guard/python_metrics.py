import ast,json,sys,tokenize,io
source=sys.stdin.read(); out={}
def report(key,value,limit,line):
    if value>limit: out[key]={'value':value,'count':1,'line':line,'message':'%s: %s > %s'%(key,value,limit)}
try:
    tree=ast.parse(source)
    code_lines={t.start[0] for t in tokenize.generate_tokens(io.StringIO(source).readline) if t.type not in (tokenize.COMMENT,tokenize.NL,tokenize.NEWLINE,tokenize.INDENT,tokenize.DEDENT,tokenize.ENDMARKER)}
    report('max-lines:file',len(code_lines),500,1)
    def visit(node,scope=''):
        name=scope
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            name=scope+'.'+node.name
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            report('max-lines-per-function:'+name,len([n for n in code_lines if node.lineno<=n<=node.end_lineno]),80,node.lineno)
            branches=sum(isinstance(n,(ast.If,ast.For,ast.AsyncFor,ast.While,ast.ExceptHandler,ast.IfExp)) for n in ast.walk(node))
            report('complexity:'+name,1+branches,15,node.lineno)
        for child in ast.iter_child_nodes(node): visit(child,name)
    visit(tree)
except (SyntaxError,tokenize.TokenError,IndentationError) as e:
    out['parse']={'value':1,'count':1,'line':getattr(e,'lineno',1),'message':str(e)}
print(json.dumps(out))
