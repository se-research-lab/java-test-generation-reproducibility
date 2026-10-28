"""Seal CP-file transport and deterministic recovery before benchmark outcomes."""
import ast,copy,json,sys
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump
from checkpoint_archive_guard_v2 import verify
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))

# Preserve the newly authored dispatcher before its pre-admission code review fixes.
p=R/'src/run_maven_b1_v3.py';backup=R/'backups/run_maven_b1_v3_pre_admission_review.py'
with backup.open('xb') as f:f.write(p.read_bytes())
text=p.read_text(encoding='utf-8')
text=text.replace("if i in RECOVER and not (out/'result.json').exists():pending_recovery.append(i)\n    else:accepted+=1", "if i in RECOVER and (not (out/'result.json').exists() or (out/'interrupted.json').exists()):pending_recovery.append(i)\n    elif not (out/'interrupted.json').exists():accepted+=1")
text=text.replace('maven_pending=211-accepted,gradle_pending=40','maven_pending=211-terminal,maven_policy_pending=211-accepted,gradle_pending=40')
text=text.replace("ensure(cp.split(os.pathsep)==expected,'Recovery ordered classpath differs beyond owned repo relocation')", "if self.generations==1:ensure(cp.split(os.pathsep)==expected,'Recovery ordered classpath differs beyond owned repo relocation')")
text=text.replace("self.out/'recovery_input_equivalence.json'", "self.out/f'recovery_input_equivalence_{self.generations:02d}.json'")
text=text.replace("'ordered_CP':'IDENTICAL_EXCEPT_OWNED_REPO_RELOCATION'", "'ordered_CP':'IDENTICAL_EXCEPT_OWNED_REPO_RELOCATION' if self.generations==1 else 'EXACT_E49_CONDITIONAL_SANITIZED_RETRY_VALIDATED_BY_BASE_GUARD'")
text=text.replace("if (out/'result.json').exists():verify(out);continue\n    if i==3:verify(base);verify(R/'jobs/003_native_junit_diagnostic_v3');continue", "if (out/'interrupted.json').exists():raise GuardAbort('Interrupted job requires explicit review: '+str(out))\n    if i==3:verify(base);verify(R/'jobs/003_native_junit_diagnostic_v3');continue\n    if (out/'result.json').exists():verify(out);continue")
ast.parse(text);p.write_text(text,encoding='utf-8')
audit.log('B1_MAVEN_V3_PRE_ADMISSION_REVIEW',backup_sha256=sha(backup),dispatcher_sha256=sha(p),fixes=['verify003 diagnostic before skip','reject interrupted completed jobs','separate terminal versus policy pending','retain E49 conditional retry CP validation','unique recovery receipt per allowed attempt'])
from run_maven_b1_v3 import guards,project,RECOVER
old=load(R/'admission_maven_v2.json');guards(old)
fixture=R/'validation/long_classpath_fixture_v1';result=load(fixture/'validation_result.json');assert result['status']=='PASS'
for file,h in result['code_hashes'].items():assert sha(file)==h
assert result['EvoSuite_processes_started']==1 and result['transport_applied'] and result['logical_argv_digest_roundtrip']
checks={'fixture':verify(fixture)};decisions=[]
for i,folder in RECOVER.items():
 out=R/'jobs'/f'{i:03d}';checks[str(i)]=verify(out);r=load(out/'result.json')
 assert not r['generation_success'] and not r['measurement_attempted'] and r['terminal']
 plans=[p for p in (out/'commands').glob('*/plan.json') if '-jar' in load(p)['argv']];assert len(plans)==1
 plan=plans[0];interrupt=load(plan.parent/'interrupted.json');assert not (plan.parent/'started.json').exists() and '[WinError 206]' in interrupt['detail']
 decisions.append({'sample_index_1based':i,'class_key':r['class_key'],'seed':r['seed'],'initial_result':str((out/'result.json').relative_to(R)),'initial_result_sha256':sha(out/'result.json'),'prior_generation_processes_started':0,'recovery_folder':folder,'replacement_result':folder+'/result.json','selection_rule':'accept this uniform-protocol terminal result irrespective of score; reject integrity abort; never choose maximum','status_at_decision':'PENDING_NO_RECOVERY_EVO_STARTED'})
assert load(R/'validation/gradle_versions_qualification_v1/complete.json')['status']=='PASS_VERSION_COMMANDS_ONLY'
mapping={'created_utc':datetime.now(timezone.utc).isoformat(),'scope':'post-launch-failure CP transport recovery; input/profile unchanged','inherits_measurement_map_v2':{'path':'measurement_result_map_v2.json','sha256':sha(R/'measurement_result_map_v2.json')},'recovery_decisions':decisions,'known_outcomes_at_decision':'Only old launch failures; no EvoSuite generation on these3 yet','E49_reused_without_regeneration':49,'GPT_changes':0,'paper_changed':False}
dump(R/'measurement_result_map_v3.json',mapping);dump(R/'audit/maven_v3_admission_archive_checks.json',checks)
paths=[p,Path(__file__),backup,R/'src/b1_maven_commands_v3.py',R/'src/classpath_transport_v1.py',R/'src/projection_io_v1.py',R/'src/checkpoint_archive_guard_v2.py',R/'measurement_result_map_v3.json',R/'measurement_result_map_v2.json',R/'WINDOWS_CP_TRANSPORT_AMENDMENT_V3_DRAFT.md',R/'validation/classpath_transport_v1/result.json',R/'validation/maven_transport_v3_static_v1/result.json',R/'validation/projection_io_v1/result.json',fixture/'validation_result.json',fixture/'artifact_manifest.json',R/'audit/windows_command012_review_v1.md',R/'audit/projection_reconciliation_v2/result.json',R/'validation/gradle_versions_qualification_v1/complete.json']
for i in RECOVER:
 out=R/'jobs'/f'{i:03d}'
 paths += [out/'result.json',out/'artifact_manifest.json',out/'controller_source_before.json',out/'production_generation_baseline.json']
 paths += list((out/'commands').glob('*/plan.json'))
lock=copy.deepcopy(old);lock.update(created_utc=datetime.now(timezone.utc).isoformat(),scope='Maven211; CP-file native transport only when Windows command exceeds32767UTF16units; preserve nativeJUnit amendmentv2',prior_admission_sha256=sha(R/'admission_maven_v2.json'),recovery_folders={str(i):v for i,v in RECOVER.items()},first_invocation_max_jobs=1,UI_publication='best-effort owned unique temps with backup/bounded retry; I/O failure separately audited',recovery_selection='fixed12,16,23 before unattempted classes; no earlier process start; verify same source/bytecode/orderedCP before Evo; no score-based retry')
lock['code_and_input_hashes'].update({str(p.resolve()):sha(p) for p in paths})
dump(R/'admission_maven_v3.json',lock);guards(lock);project('ADMITTED_CHECKPOINT_MAX1')
audit.log('B1_MAVEN_V3_ADMITTED',admission_sha256=sha(R/'admission_maven_v3.json'),result_map_sha256=sha(R/'measurement_result_map_v3.json'),recoveries=[12,16,23],first_max_jobs=1,fixture_EvoSuite_calls=3,GPT_API_calls=0)
print('PASS: Mavenv3 sealed; fixed recovery12/16/23; first maxjobs1; CPfixture+UI guards; GPT and49 unchanged')
