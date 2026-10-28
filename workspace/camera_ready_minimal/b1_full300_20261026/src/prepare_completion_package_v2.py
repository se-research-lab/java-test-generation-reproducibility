"""Extend private evidence package with all staged qualifications and raw Maven XML/coverage."""
import ast,difflib
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1'
def main():
 old=R/'src/package_completion_evidence_v1.py';new=R/'src/package_completion_evidence_v2.py';text=old.read_text()
 text=text.replace("'maven_junit3_run_v1']:","'maven_junit3_run_v1','maven_pom_run_v2','maven_junit3_run_v2','maven_sequence_v2','maven_sequence_v3','stage_sequence_v1','maven_qualification_v2_preparation','maven_qualification_v3_preparation','stage_completion_v4_preparation','analysis_v2_preparation','analysis_v3_preparation','history_delivery_v1']:")
 before="for r in rows:\n  if r['selected_result']:folders.add(Path(r['selected_result']['path']).parent)"
 after="""for r in rows:
  if r['selected_result']:folders.add(Path(r['selected_result']['path']).parent)
  if r.get('module'):
   module=Path(r['module']);base='selected_raw/'+f"{r['index']:03d}/"
   for pattern in ['target/surefire-reports/TEST-*.xml','target/site/jacoco/jacoco.csv','target/pit-reports/**/mutations.csv']:
    for p in module.glob(pattern):
     if p.is_file():add(p,base+p.relative_to(module).as_posix())
   fqcn=r.get('selected_test_fqcn','')
   if fqcn:
    source=module/'src/test/java'/Path(*fqcn.split('.')).with_suffix('.java')
    for p in [source,source.with_name(source.stem+'_scaffolding.java')]:
     if p.is_file():add(p,base+'native_suite/'+p.name)
   for name in ['pom.xml','build.gradle','build.gradle.kts']:
    p=module/name
    if p.is_file():add(p,base+'build_configuration/'+name)"""
 assert before in text;text=text.replace(before,after)
 before="oldhistory=R/'policy_attempt_history_v2'"
 after="""for folder in (R/'validation').glob('completion_maven_*_v*'):
  for p in folder.rglob('*'):
   rel=p.relative_to(folder)
   if p.is_file() and not any(s in rel.parts for s in ['repo','temp']) and p.name!='settings.xml':add(p,'qualification/'+folder.name+'/'+rel.as_posix())
 for p in [R/'manifest300.json',R/'protocol.json',R/'inputs/context251_v1/manifest.json',R/'inputs/gradle40_context_v2/manifest.json',R/'inputs/snapshot_v3/index.json']:
  add(p,'reproduction_inputs/'+p.relative_to(R).as_posix())
 for p in [R.parent/'paired49_20261023/audit.py']:
  add(p,'audit_runtime/'+p.name)
 oldhistory=R/'policy_attempt_history_v2'"""
 assert before in text;text=text.replace(before,after)
 ast.parse(text)
 with new.open('x',encoding='utf-8') as f:f.write(text)
 out=A/'package_v2_preparation';out.mkdir();(out/'change.diff').write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8');dump(out/'receipt.json',{'new_sha256':sha(new),'scope':'private evidence package only; no execution'})
 print('Prepared private packager with raw XML, coverage and unchanged native source copies')
if __name__=='__main__':main()
