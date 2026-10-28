"""Private bounded evidence ZIP: reports, command logs, policies and source. No API inputs."""
import json,re,sys,zipfile
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
 analysis=A/'analysis_v2';assert (analysis/'MANIFEST.json').exists(),'Final pass audit required'
 out=A/'delivery_v2';out.mkdir(exist_ok=False);files={}
 def add(p,rel):
  p=Path(p);assert p.is_file() and not p.is_symlink();assert rel not in files or files[rel]==p;files[rel]=p
 for p in analysis.rglob('*'):
  if p.is_file():add(p,'analysis/'+p.relative_to(analysis).as_posix())
 for p in A.glob('*.md'):add(p,p.name)
 for p in A.glob('admission_*.json'):add(p,'admissions/'+p.name)
 for name in ['input_audit','dispatcher_v2_preparation','qualification_preparation','pom_preparation','gradle_pit_run_v1','gradle_pit_run_v2','maven_sequence_v1','maven_pom_run_v1','maven_junit3_run_v1','maven_pom_run_v2','maven_junit3_run_v2','maven_sequence_v2','maven_sequence_v3','stage_sequence_v1','maven_qualification_v2_preparation','maven_qualification_v3_preparation','stage_completion_v4_preparation','analysis_v2_preparation','analysis_v3_preparation','history_delivery_v2','result_reconciliations_v1','partial_pit_preparation_v1','remaining_pom8_launch_v1','maven_pom_run_v3','remaining8_finalization_preparation_v1']:
  folder=A/name
  for p in folder.rglob('*'):
   if p.is_file():add(p,'audit/'+name+'/'+p.relative_to(folder).as_posix())
 # All local controller source and adapters, without runtime caches or credentials.
 for source in [R/'src',R/'adapters']:
  for p in source.glob('*.py'):add(p,'code/'+source.name+'/'+p.name)
 for p in (R/'backups/accepted49_adapter/src').glob('*.py'):add(p,'code/frozen_e49_helpers/'+p.name)
 for folder in (R/'validation').glob('completion_maven_*_v*'):
  for p in folder.rglob('*'):
   rel=p.relative_to(folder)
   if p.is_file() and not any(s in rel.parts for s in ['repo','temp']) and p.name!='settings.xml':add(p,'qualification/'+folder.name+'/'+rel.as_posix())
 for p in [R/'manifest300.json',R/'protocol.json',R/'inputs/context251_v1/manifest.json',R/'inputs/gradle40_context_v2/manifest.json',R/'inputs/snapshot_v3/index.json']:
  add(p,'reproduction_inputs/'+p.relative_to(R).as_posix())
 for p in [R.parent/'paired49_20261023/audit.py']:
  add(p,'audit_runtime/'+p.name)
 oldhistory=R/'policy_attempt_history_v2'
 for n in ['class_policy_history300.csv','command_history_all.csv','generation_measurement_diagnostic_attempts.csv','policy_timeline.csv','dependency_selector_changes.csv','selection_current.json','METHODS_ENVIRONMENT_ASYMMETRY.md']:
  add(oldhistory/n,'history_before_amendment/'+n)
 rows=load(analysis/'class_results300.json');folders=set()
 for r in rows:
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
    if p.is_file():add(p,base+'build_configuration/'+name)
 for d in load(analysis/'attempts_addendum.json'):folders.add(Path(d['folder']))
 for k,folder in enumerate(sorted(folders)):
  base=f'job_evidence/{k:03d}_{folder.name}/'
  for p in folder.glob('*.json'):
   if p.name not in ['environment_allowlist.json']:add(p,base+p.name)
  for p in folder.glob('command_??*'):
   if p.is_file():add(p,base+p.name)
  for sub in ['commands','command_admissions','generation_attempts','recipes']:
   for p in (folder/sub).rglob('*'):
    if p.is_file() and p.suffix.lower() in {'.json','.jsonl','.txt','.csv','.xml','.gradle','.java','.diff'}:add(p,base+sub+'/'+p.relative_to(folder/sub).as_posix())
  for p in folder.glob('*.diff'):add(p,base+p.name)
 # Actual token/private-key signatures, not variable names from safety guards.
 patterns=[re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),re.compile(rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{32,}'),re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30,}'),re.compile(rb'\bAKIA[A-Z0-9]{16}\b')]
 suspect=[]
 for rel,p in files.items():
  if any(x in rel.lower() for x in ['api_prompts','api_log.csv','settings.xml','.env']):raise AssertionError('Excluded artifact name: '+rel)
  data=p.read_bytes()
  if any(pattern.search(data) for pattern in patterns):suspect.append(rel)
 assert not suspect,'Potential secret found; package not written: '+str(suspect)
 manifest=[{'archive_path':rel,'source_path':str(p.resolve()),'sha256':sha(p),'bytes':p.stat().st_size} for rel,p in sorted(files.items())]
 dump(out/'PACKAGE_MANIFEST.json',manifest)
 zpath=out/'E1_completion_private_evidence_v2.zip'
 with zipfile.ZipFile(zpath,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for rel,p in sorted(files.items()):z.write(p,rel)
  z.write(out/'PACKAGE_MANIFEST.json','PACKAGE_MANIFEST.json')
 with zipfile.ZipFile(zpath) as z:
  import hashlib
  assert z.testzip() is None
  for row in manifest:assert hashlib.sha256(z.read(row['archive_path'])).hexdigest()==row['sha256']
 dump(out/'verification.json',{'status':'PASS_PRIVATE_EVIDENCE_ZIP','files':len(files),'zip_sha256':sha(zpath),'zip_bytes':zpath.stat().st_size,'all_members_rehashed':True,'secret_signature_scan':'PASS; bounded signature scan, not a guarantee about all possible secrets','public_release':False,'full300_complete':load(analysis/'statistics.json')['full300_complete'],'standalone_reexecution_without_private_provisioned_inputs_tested':False})
 (out/'SHA256SUMS.txt').write_text(sha(zpath)+'  '+zpath.name+'\n',encoding='ascii')
 print('Packaged',len(files),'files',zpath.stat().st_size,'bytes')
if __name__=='__main__':main()
