"""Require selected evidence to match sealed job archives before final reconciliation."""
import ast,difflib
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1'
def main():
 old=R/'src/audit_completion_results_v3.py';new=R/'src/audit_completion_results_v4.py';text=old.read_text()
 needle='def evidence(j,path):\n d=load(path);folder=path.parent;cmd=commands(folder)'
 replacement='''def evidence(j,path):
 d=load(path);folder=path.parent
 manifest=folder/'artifact_manifest.json'
 assert manifest.is_file(),'Selected result lacks sealed job archive'
 archive=load(manifest)
 assert isinstance(archive,list),'Unexpected archive schema'
 entries={row['relative']:row for row in archive}
 # Verify result and the actual command/report/native evidence. The original
 # benchmark source/bytecode guards remain archived; do not infer from scores.
 required=[]
 for rel,row in entries.items():
  parts=Path(rel).parts
  evidence_file=(rel=='result.json' or rel=='diagnostic_result.json' or rel.startswith(('commands/','command_admissions/','recipes/')) or Path(rel).name in {'mutations.csv','jacoco.csv','native_generated.json','suite_reuse.json','production_bytecode_guard.json'} or Path(rel).name.startswith('TEST-') and Path(rel).suffix=='.xml' or Path(rel).name.endswith(('_ESTest.java','_ESTest_scaffolding.java')) or Path(rel).name.startswith('command_') and Path(rel).suffix in {'.json','.txt'})
  if evidence_file:required.append((folder/rel,row['sha256']))
 assert path.relative_to(folder).as_posix() in entries,'Selected result not sealed'
 verify_pins({str(p):h for p,h in required})
 cmd=commands(folder)'''
 assert needle in text;text=text.replace(needle,replacement)
 ast.parse(text)
 with new.open('x',encoding='utf-8') as f:f.write(text)
 out=A/'analysis_v4_preparation';out.mkdir();(out/'change.diff').write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8');dump(out/'receipt.json',{'old_sha256':sha(old),'new_sha256':sha(new),'scope':'offline selected evidence archive verification only'})
 oldf=R/'src/finalize_completion_when_ready_v1.py';newf=R/'src/finalize_completion_when_ready_v2.py';t=oldf.read_text().replace("O=A/'automatic_finalization_v1'","O=A/'automatic_finalization_v2'").replace('audit_completion_results_v3.py','audit_completion_results_v4.py')
 ast.parse(t)
 with newf.open('x',encoding='utf-8') as f:f.write(t)
 (out/'finalizer.diff').write_text(''.join(difflib.unified_diff(oldf.read_text().splitlines(True),t.splitlines(True),fromfile=oldf.name,tofile=newf.name)),encoding='utf-8')
 print('Prepared archive-verifying offline audit and finalizer v2')
if __name__=='__main__':main()
