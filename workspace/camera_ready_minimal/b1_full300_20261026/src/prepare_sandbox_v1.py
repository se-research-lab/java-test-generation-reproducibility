"""Materialize a new E-only job from a completed B1 snapshot, never edit originals."""
import json,sqlite3,shutil,sys,os
from pathlib import Path
from snapshot_store_v1 import restore,safe_relative,IntegrityError
from maven_adapter_v1 import R,sha,dump,GuardAbort,new_job_output
E49_EXCLUDED={'.git','.gradle','.evosuite','target','build','evosuite-tests','evosuite-report'}
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def prepare(index,out,snapshot_dir):
 out=new_job_output(out);S=Path(snapshot_dir).resolve()
 if not S.is_relative_to((R/'inputs').resolve()):raise GuardAbort('Snapshot outside B1 inputs')
 completion=load(S/'complete.json')
 if completion['status']!='PASS' or not completion['every_blob_rehashed']:raise GuardAbort('Snapshot not completely verified')
 if sha(S/'index.json')!=completion['index_sha256']:raise GuardAbort('Snapshot index drift')
 jobs=load(R/'manifest300.json');j=next(x for x in jobs if x['sample_index_1based']==index)
 if j['reused_result']:raise GuardAbort('Accepted49 cannot be rematerialized as new benchmark')
 mapping=next(x for x in load(S/'index.json') if index in x['class_indices']);p=R/mapping['manifest']
 if sha(p)!=mapping['sha256']:raise GuardAbort('Snapshot manifest drift')
 data=load(p);context=next(x for x in load(R/'inputs/context251_v1/manifest.json') if x['sample_index_1based']==index)
 if not context['framework_found']:raise GuardAbort('Framework metadata unavailable')
 if out.exists():raise GuardAbort('New job output required; no implicit resume')
 out.mkdir(parents=True,exist_ok=False)
 # Materialize source policy identical to E49; the larger backup retains all omitted bytes.
 included=[];excluded=[]
 for row in data['files']:
  rel=safe_relative(row['relative'])
  (excluded if any(part in E49_EXCLUDED for part in rel.parts[:-1]) else included).append(row)
 with sqlite3.connect((S/'content.sqlite3').as_uri()+'?mode=ro',uri=True) as conn:
  restore(conn,included,out/'repo')
  if data['settings']:
   restore(conn,[data['settings']],out/'context_snapshot')
   source=out/'context_snapshot'/data['settings']['relative'];dest=out/'settings.xml'
   with source.open('rb') as f,dest.open('xb') as t:shutil.copyfileobj(f,t)
   if sha(dest)!=data['settings']['sha256']:raise GuardAbort('Settings restore mismatch')
 dump(out/'input_snapshot_manifest.json',included);dump(out/'excluded_backup_paths.json',excluded)
 prior=safe_relative(context['prior_synthesized_test_relative']);old=out/'repo'/prior;quarantine=[]
 if old.is_file():
  dest=out/'prior_test_evidence'/prior;dest.parent.mkdir(parents=True,exist_ok=True)
  # Verify paths before a move; only a copied file inside the exact new job may move.
  if not old.resolve().is_relative_to((out/'repo').resolve()) or not dest.resolve().is_relative_to(out.resolve()):raise GuardAbort('Prior-test quarantine path escape')
  h=sha(old);old.rename(dest)
  if sha(dest)!=h:raise GuardAbort('Prior-test quarantine bytes differ')
  quarantine.append({'relative':prior.as_posix(),'backup':dest.relative_to(out).as_posix(),'sha256':h})
 dump(out/'quarantined_prior_test.json',quarantine)
 stale=[p.relative_to(out/'repo').as_posix() for p in (out/'repo').rglob('*.java') if '/src/test/java/' in '/'+p.as_posix() and p.name.endswith(('_ESTest.java','_ESTest_scaffolding.java'))]
 if stale:
  dump(out/'stale_native_test_block.json',stale);raise GuardAbort('Prior native EvoSuite tests require separate provenance review; no silent deletion')
 focal=out/'repo'/safe_relative(j['focal_path']);module=out/'repo'
 if j['module'] not in {'','.'}:module/=safe_relative(j['module'])
 if sha(focal)!=j['source_candidate']['focal_sha256']:raise GuardAbort('Restored focal drift')
 result={'class_key':j['class_key'],'sample_index_1based':index,'seed':j['seed'],'module':str(module),'focal':str(focal),'snapshot_manifest_sha256':mapping['sha256'],'source_store_sha256_at_completion':completion['store_sha256'],'restored_file_count':len(included),'quarantined_prior_tests':len(quarantine),'excluded_file_count':len(excluded),'context':context,'generation_calls':0,'measurement_calls':0,'benchmark_admitted':False}
 dump(out/'sandbox_preparation.json',result);return result

if __name__=='__main__':
 raise SystemExit('Import only from an audited controller after snapshot completion; no batch entry point.')
