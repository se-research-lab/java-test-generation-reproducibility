"""Parse B1 sources without executing their module bodies or importing project code."""
import ast,json,hashlib
from pathlib import Path
R=Path(__file__).resolve().parents[1];rows=[]
for p in sorted((R/'src').glob('*.py')):
 tree=ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
 imports=[]
 for n in ast.walk(tree):
  if isinstance(n,ast.Import):imports.extend(a.name for a in n.names)
  elif isinstance(n,ast.ImportFrom):imports.append(n.module or '')
 assert not any(x.split('.')[0] in {'openai','anthropic','rbl4_v2_runner','agone_test'} for x in imports),p
 rows.append({'path':p.relative_to(R).as_posix(),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'syntax':'PASS','imports':sorted(set(imports))})
report={'status':'PASS','files':rows,'experiment_calls':0,'note':'Syntax and explicit import check only, not an execution-safety proof'}
out=R/'validation/source_syntax_v1';out.mkdir(parents=True,exist_ok=False)
with (out/'result.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
print(json.dumps({'status':'PASS','parsed_sources':len(rows),'experiment_calls':0},indent=2))
