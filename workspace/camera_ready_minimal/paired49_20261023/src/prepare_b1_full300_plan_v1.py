"""Read-only E300 admission inventory. Never imports or runs any generator."""
import csv,json,hashlib,sys,shutil,subprocess,re
from pathlib import Path
from datetime import datetime,timezone
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
ROOT=B.parents[1];R=ROOT/'camera_ready_minimal/b1_full300_20261026';assert not (R/'manifest300.json').exists()
R.mkdir(parents=True,exist_ok=True)
def rows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def dump(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
def now():return datetime.now(timezone.utc).isoformat()
run=ROOT/'scripts_v2/results/runs/full300_merged_20260724_paper'
samples=rows(ROOT/'scripts_v2/data_new/class_sampling_manifest_final_seed42.csv');wide=rows(run/'metrics_wide.csv');staged={r['class_key']:r for r in rows(run/'generation_classes.csv')};generated=rows(run/'generated_tests_manifest.csv')
assert len(samples)==300 and len({r['class_key'] for r in samples})==300
assert {r['class_key'] for r in samples}=={r['class_key'] for r in wide}
e49=json.loads((B/'e49_driver/input_manifest49.json').read_text());old={j['class_key']:j for j in e49};assert len(old)==49
registry_counts={}
for n in ['measurement49_camera_ready_registry_v1.json','camera_ready_response_registry_v1.json','disclosure_only_registry_v1.json']:
 reg=json.loads((B/'audit'/n).read_text());
 for x in reg['files']:assert audit.sha(B/x['path'])==x['sha256'],x['path']
 registry_counts[n]=len(reg['files'])
guard=ROOT/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py'
g=subprocess.run([sys.executable,'-B','-X','utf8',str(guard)],capture_output=True,text=True,encoding='utf-8');assert g.returncode==0,g.stderr;gr=json.loads(g.stdout);assert gr['status']=='PASS';dump(R/'audit/GPT_guard_initial.json',gr)
audit.verify();jobs=[];provenance=[]
for i,s in enumerate(samples,1):
 key=s['class_key'];hist=staged[key];reuse=old.get(key);candidate_roots=[]
 if reuse:candidate_roots.append(Path(reuse['source_repo']))
 for r in generated:
  if r['class_key']!=key:continue
  p=Path(r.get('original_source_path') or r.get('source_path',''))
  if 'output' in p.parts:
   idx=p.parts.index('output');candidate_roots.append(Path(*p.parts[:idx])/'compiledrepos'/s['repo_id'])
 readiness=Path(hist.get('sandbox_readiness_path',''))
 if str(readiness) not in ['','.']:candidate_roots.append(readiness/'compiledrepos'/s['repo_id'])
 candidate_roots.append(ROOT/'compiledrepos'/s['repo_id'])
 found=[];seen=set()
 for root in candidate_roots:
  if str(root) in seen:continue
  seen.add(str(root));p=root/s['focal_path']
  if p.is_file():found.append({'source_repo':str(root),'focal_sha256':audit.sha(p),'focal_bytes':p.stat().st_size,'shared_compiledrepos':root==ROOT/'compiledrepos'/s['repo_id']})
 canonical=found[0] if found else None
 reusable=False;evidence={}
 if reuse:
  assert reuse['sample_index']==i and reuse['seed']==20261023+i
  folder=B/'e49_measurement_compat_v1/jobs'/f"{reuse['job_index']:02d}"
  artifacts=json.loads((folder/'artifact_manifest.json').read_text())
  for x in artifacts:assert audit.sha(B/x['path'])==x['sha256'],x['path']
  result=json.loads((folder/'result.json').read_text());assert result['class_key']==key and result['seed']==reuse['seed']
  assert canonical and canonical['focal_sha256']==reuse['focal_sha256']
  reusable=True;evidence={'old_job_index':reuse['job_index'],'result_path':str(folder/'result.json'),'result_sha256':audit.sha(folder/'result.json'),'artifact_manifest_path':str(folder/'artifact_manifest.json'),'artifact_manifest_sha256':audit.sha(folder/'artifact_manifest.json'),'verified_evidence_files':len(artifacts),'generation_profile_sha256':audit.sha(B/'e49_driver/protocol49.json'),'measurement_policy_sha256':audit.sha(B/'e49_measurement_compat_v1/protocol.json')}
 job={'sample_index_1based':i,'class_key':key,'repo_id':s['repo_id'],'repo_url':s['repo_url'],'commit_sha':s['commit_sha'],'focal_class':s['focal_class'],'focal_path':s['focal_path'],'module':hist['Module'],'build_tool':s['build_tool'].lower(),'seed':20261023+i,'status':'REUSED_VERIFIED_E49' if reusable else ('PENDING_MAVEN_QUALIFICATION' if s['build_tool'].lower()=='maven' else 'BLOCKED_GRADLE_QUALIFICATION'),'source_candidate':canonical,'source_candidates':found,'focal_candidate_hash_agreement':len({x['focal_sha256'] for x in found})<=1 if found else None,'complete_source_snapshot_frozen':False,'reused_result':evidence,'new_generation_calls':0,'new_measurement_calls':0}
 jobs.append(job)
assert sum(j['status']=='REUSED_VERIFIED_E49' for j in jobs)==49
assert sum(j['status']=='PENDING_MAVEN_QUALIFICATION' for j in jobs)==211
assert sum(j['status']=='BLOCKED_GRADLE_QUALIFICATION' for j in jobs)==40
dump(R/'manifest300.json',jobs)
protected=[]
for p in [ROOT/'scripts_v2/data_new/class_sampling_manifest_final_seed42.csv',run/'metrics_wide.csv',run/'metrics_long.csv',run/'generated_tests_manifest.csv',B/'e49_driver/input_manifest49.json',B/'e49_driver/protocol49.json',B/'e49_measurement_compat_v1/protocol.json',B/'repeated_subset_v1/STOP_DO_NOT_RESUME.json',B/'final_handoff_20261025_private/RELEASE_MANIFEST.json',guard,Path(__file__)]:
 protected.append({'path':str(p),'sha256':audit.sha(p),'bytes':p.stat().st_size})
dump(R/'audit/input_lock.json',protected)
dump(R/'authorization.json',{'recorded_utc':now(),'source':'User request 2026-10-26: plan and begin B1 full300 EvoSuite with guards, continuity from49 and web preview','E300_scope_reopened':True,'GPT_generation_or_remeasurement_authorized':False,'repeated_subset_resume_authorized':False,'public_code_release_authorized':False,'original_stop_record_preserved':True,'benchmark_admission':'NOT_READY; new execution requires technical qualification, not another outcome-based choice'})
dump(R/'reuse49_admission.json',{'status':'PASS_FOR_ARCHIVED_FINAL_E49','n':49,'registry_counts':registry_counts,'basis':'exact cohort keys, sampling index seeds, final result and all registered raw-evidence hashes','future_union_condition':'remaining251 must use the frozen compatible protocol; no E0 rows substituted. Any profile amendment invalidating compatibility requires separate version/cohort decision, not silent reuse','post_hoc_scope_extension':True,'outcomes_E49_already_known':True,'new_experiment_calls':0})
profile={'status':'DESIGN_LOCKED_EXECUTION_NOT_ADMITTED','target_n':300,'reuse49':49,'new_maven211':211,'new_gradle40':40,'workers':1,'seed_rule':'20261023 + original sampling manifest 1-based row index','search_budget_seconds':60,'generation_timeout_seconds':240,'max_generation_attempts':2,'retry':'one conditional sanitized-classpath technical retry, same seed; never choose highest score','measurement_timeout_seconds':300,'dependency_timeout_seconds':180,'generation_options':['-Dassertions=true','-Dassertion_strategy=MUTATION','-Dtest_scaffolding=true','-Dno_runtime_dependency=false','-Dcriterion=BRANCH','-Dsearch_budget=60','-Dtest_archive=false','-Duse_separate_classloader=false'],'measurement_policy':'inherit accepted E49 policy; raw BUILD SUCCESS/no timeout process gate and KILLED/all focal SourceFile+package incl nested, rounded2, zero-fill only after actual terminal execution outcomes','JUnit_selector_policy_source_sha256':audit.sha(B/'e49_measurement_compat_v1/protocol.json'),'Maven_status':'adapter and copied-source freeze pending; no admission yet','Gradle_status':'separate E-only adapter qualification required; native scaffold/runtime and JUnit vs TestNG isolation unresolved; no fallback zero for unattempted classes','GPT':'no API, no remeasurement, no shared runner/dependency edits, retain61/45/300 and298+2','claim':'post-review single-run full-cohort extension if all300 terminal and audit PASS; not default-all-options EvoSuite, not repeated variance or assertion-only causal effect'}
dump(R/'protocol.json',profile)
summary={'phase':'PREFLIGHT / PLAN','updated_utc':now(),'target':300,'reused_verified':49,'new_completed':0,'running':0,'maven_pending':211,'gradle_pending':40,'new_API_calls':0,'new_EvoSuite_calls':0,'GPT_guard':'PASS','reuse49_guard':'PASS','benchmark_admitted':False,'missing_focal_candidates':sum(j['source_candidate'] is None for j in jobs),'focal_candidate_disagreements':sum(j['focal_candidate_hash_agreement'] is False for j in jobs),'disk_free_GB':round(shutil.disk_usage(ROOT).free/1e9,2),'blockers':['Freeze complete source snapshots and copied E-only runner','Qualify Maven E49-compatible adapter on synthetic controls','Qualify Gradle classpath, native scaffold/runtime and test discovery','Pass negative guards, stop/resume and archive capacity checks'],'tasks':[{'id':'B1.0','name':'Khóa300 keys và ghi nhận mở lại E-only','status':'DONE'},{'id':'B1.1','name':'Xác minh reuse49 và GPT guard','status':'DONE'},{'id':'B1.2','name':'Đóng băng source và adapter Maven211','status':'PENDING'},{'id':'B1.3','name':'Tích hợp E-only Gradle40 và kiểm framework','status':'BLOCKED'},{'id':'B1.4','name':'Fixture, negative guards, admission lock','status':'PENDING'},{'id':'B1.5','name':'Chạy251 còn lại, serial, giữ mọi failures','status':'NOT_STARTED'},{'id':'B1.6','name':'Audit300 và phân tích RQ4/RQ5 riêng','status':'NOT_STARTED'}]}
dump(R/'status.json',summary)
event={'timestamp_utc':now(),'kind':'B1_SCOPE_AND_REUSE_ADMISSION','data':summary};(R/'events.jsonl').write_text(json.dumps(event,ensure_ascii=False)+'\n',encoding='utf-8')
audit.log('B1_FULL300_PLAN_INITIALIZED',stage=str(R),manifest_sha256=audit.sha(R/'manifest300.json'),reuse49=49,new_jobs=251,GPT_guard=gr,benchmark_admitted=False)
print(json.dumps(summary,ensure_ascii=False,indent=2))
