"""Private bounded evidence ZIP: reports, command logs, policies and source. No API inputs."""
import json,re,sys,zipfile
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
 analysis=A/'analysis_v1';assert (analysis/'MANIFEST.json').exists(),'Final pass audit required'
 out=A/'delivery_v1';out.mkdir(exist_ok=False);files={}
 def add(p,rel):
  p=Path(p);assert p.is_file() and not p.is_symlink();assert rel not in files or files[rel]==p;files[rel]=p
 for p in analysis.rglob('*'):
  if p.is_file():add(p,'analysis/'+p.relative_to(analysis).as_posix())
 for p in A.glob('*.md'):add(p,p.name)
 for p in A.glob('admission_*.json'):add(p,'admissions/'+p.name)
 for name in ['input_audit','dispatcher_v2_preparation','qualification_preparation','pom_preparation','gradle_pit_run_v1','gradle_pit_run_v2','maven_sequence_v1','maven_pom_run_v1','maven_junit3_run_v1']:
  folder=A/name
  for p in folder.rglob('*'):
   if p.is_file():add(p,'audit/'+name+'/'+p.relative_to(folder).as_posix())
 # All local controller source and adapters, without runtime caches or credentials.
 for source in [R/'src',R/'adapters']:
  for p in source.glob('*.py'):add(p,'code/'+source.name+'/'+p.name)
 for p in (R/'backups/accepted49_adapter/src').glob('*.py'):add(p,'code/frozen_e49_helpers/'+p.name)
 oldhistory=R/'policy_attempt_history_v2'
 for n in ['class_policy_history300.csv','command_history_all.csv','generation_measurement_diagnostic_attempts.csv','policy_timeline.csv','dependency_selector_changes.csv','selection_current.json','METHODS_ENVIRONMENT_ASYMMETRY.md']:
  add(oldhistory/n,'history_before_amendment/'+n)
 rows=load(analysis/'class_results300.json');folders=set()
 for r in rows:
  if r['selected_result']:folders.add(Path(r['selected_result']['path']).parent)
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
 zpath=out/'E1_completion_private_evidence_v1.zip'
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
