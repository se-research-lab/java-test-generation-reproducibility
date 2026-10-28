"""Synthetic-only restore/quarantine fixtures; no original manifest is edited."""
import json
from pathlib import Path
import prepare_sandbox_v1 as p
from snapshot_store_v1 import open_new_store,capture_file
from maven_adapter_v1 import R,sha,dump,GuardAbort
O=R/'validation/prepare_sandbox_v1';O.mkdir(parents=True,exist_ok=False)
fixture=O/'isolated_fixture';fixture.mkdir();source=fixture/'historical_source';(source/'src/main/java/fixture').mkdir(parents=True);(source/'src/test/java/fixture').mkdir(parents=True);(source/'target').mkdir()
focal=source/'src/main/java/fixture/A.java';focal.write_text('package fixture; class A {}',encoding='utf-8')
oldtest=source/'src/test/java/fixture/A_RBL4Test_old.java';oldtest.write_text('// prior test bytes',encoding='utf-8');(source/'target/stale.xml').write_text('stale',encoding='utf-8')
S=fixture/'inputs/snapshot';S.mkdir(parents=True);c=open_new_store(S/'content.sqlite3');rows=[capture_file(c,source,x) for x in ['src/main/java/fixture/A.java','src/test/java/fixture/A_RBL4Test_old.java','target/stale.xml']];c.commit();c.close()
data={'files':rows,'settings':None,'class_indices':[1]};dump(S/'manifest.json',data)
dump(S/'index.json',[{'class_indices':[1],'manifest':'inputs/snapshot/manifest.json','sha256':sha(S/'manifest.json')}])
dump(S/'complete.json',{'status':'PASS','every_blob_rehashed':True,'index_sha256':sha(S/'index.json'),'store_sha256':sha(S/'content.sqlite3')})
dump(fixture/'manifest300.json',[{'sample_index_1based':1,'class_key':'synthetic:A','seed':20261024,'module':'','focal_path':'src/main/java/fixture/A.java','source_candidate':{'focal_sha256':sha(focal)},'reused_result':{}},{'sample_index_1based':2,'class_key':'synthetic:reused','reused_result':{'accepted':True}}])
dump(fixture/'inputs/context251_v1/manifest.json',[{'sample_index_1based':1,'framework_found':True,'prior_synthesized_test_relative':'src/test/java/fixture/A_RBL4Test_old.java'}])
original_root=p.R;p.R=fixture # Scoped fixture dependency injection; actual R manifest untouched.
try:
 out=O/'materialized';result=p.prepare(1,out,S)
 assert (out/'repo/src/main/java/fixture/A.java').read_bytes()==focal.read_bytes()
 assert oldtest.exists() and not (out/'repo/src/test/java/fixture/A_RBL4Test_old.java').exists()
 assert (out/'prior_test_evidence/src/test/java/fixture/A_RBL4Test_old.java').read_bytes()==oldtest.read_bytes()
 assert not (out/'repo/target').exists()
 checks=['source_exactly_restored','original_prior_test_unchanged','copied_prior_test_quarantined_with_hash','stale_target_excluded_backup_retained']
 for name,fn in [('rerun_output_rejected',lambda:p.prepare(1,out,S)),('accepted49_rejected',lambda:p.prepare(2,O/'accepted_reuse',S)),('external_snapshot_rejected',lambda:p.prepare(1,O/'escape',R.parent))]:
  try:fn()
  except GuardAbort:checks.append(name)
  else:raise AssertionError(name)
finally:p.R=original_root
report={'status':'PASS','checks':checks,'scope':'synthetic store and synthetic manifest under validation only; original manifest untouched','generation_calls':0,'measurement_calls':0,'helper_sha256':sha(R/'src/prepare_sandbox_v1.py')};dump(O/'result.json',report);print(json.dumps(report,indent=2))
