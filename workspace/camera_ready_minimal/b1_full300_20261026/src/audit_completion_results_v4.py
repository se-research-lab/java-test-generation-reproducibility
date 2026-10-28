"""Offline 300-row evidence reconciliation; never starts tools or edits a manuscript."""
import argparse,csv,json,hashlib,shutil,re,sys
from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
import numpy as np
from maven_adapter_v1 import R,sha,dump
from parallel_pin_verify_v1 import verify_pins
from run_maven_b1_v3 import guards
A=R/'completion_amendment_v1';B=R.parent/'paired49_20261023'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def pin(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def commands(folder):
 rows=[]
 for p in sorted((folder/'commands').glob('*/plan.json')):
  plan=load(p);finish=p.parent/'finished.json';end=load(finish) if finish.exists() else {}
  argv=plan['argv'];kind='generation' if '-jar' in argv else 'mutation_measurement' if any('mutationCoverage' in a or a.endswith('pitest') for a in argv) else 'test_execution' if any(a.endswith('b1NativeTest') for a in argv) else 'compile_or_dependency_audit'
  rows.append({'plan':pin(p),'kind':kind,'argv':argv,'cwd':plan.get('cwd'),'timeout_seconds':plan.get('timeout_seconds'),'started':(p.parent/'started.json').exists(),'returncode':end.get('returncode'),'timeout':end.get('reason')=='TIMEOUT','finished':finish.exists(),'logs':[pin(p.parent/n) for n in ['stdout.txt','stderr.txt'] if (p.parent/n).exists()]})
 for p in sorted(folder.glob('command_??.json')):
  d=load(p);argv=d.get('argv',[])
  rows.append({'plan':pin(p),'kind':'mutation_measurement' if any('mutationCoverage' in x for x in argv) else 'compile_or_dependency_audit','argv':argv,'cwd':d.get('cwd'),'started':True,'returncode':d.get('returncode'),'timeout':d.get('timeout',False),'finished':True,'logs':[pin(folder/(p.stem+s)) for s in ['.stdout.txt','.stderr.txt'] if (folder/(p.stem+s)).exists()]})
 return rows
def evidence(j,path):
 d=load(path);folder=path.parent
 manifest=folder/'artifact_manifest.json'
 if not manifest.is_file():  assert folder.resolve()==(R/'jobs/066').resolve(),'Selected result lacks sealed job archive: '+str(folder)  from completed_archive_guard_v3 import verify as verify_recovered66  verify_recovered66(folder)  recovery=load(R/'audit/absent_v4_runner_reconciliation_v1/result.json')  manifest=R/recovery['external_archive_path']  assert sha(manifest)==recovery['external_archive_sha256'],'Existing external066 archive drift'
 archive=load(manifest)
 assert isinstance(archive,list),'Unexpected archive schema'
 entries={}
 for row in archive:
  item=folder/row['relative'] if 'relative' in row else B/row['path']
  rel=item.resolve().relative_to(folder.resolve()).as_posix()
  assert rel not in entries,'Duplicate archive key'
  entries[rel]=row
 # Verify result and the actual command/report/native evidence. The original
 # benchmark source/bytecode guards remain archived; do not infer from scores.
 required=[]
 for rel,row in entries.items():
  parts=Path(rel).parts
  evidence_file=(rel=='result.json' or rel=='diagnostic_result.json' or rel.startswith(('commands/','command_admissions/','recipes/')) or Path(rel).name in {'mutations.csv','jacoco.csv','native_generated.json','suite_reuse.json','production_bytecode_guard.json'} or Path(rel).name.startswith('TEST-') and Path(rel).suffix=='.xml' or Path(rel).name.endswith(('_ESTest.java','_ESTest_scaffolding.java')) or Path(rel).name.startswith('command_') and Path(rel).suffix in {'.json','.txt'})
  if evidence_file:required.append((folder/rel,row['sha256']))
 assert path.relative_to(folder).as_posix() in entries,'Selected result not sealed'
 verify_pins({str(p):h for p,h in required})
 cmd=commands(folder)
 measure=[c for c in cmd if c['kind']=='mutation_measurement']
 # Resolve the actual module from logged lifecycle cwd (E49 uses its own snapshot root).
 module=Path(measure[-1]['cwd']) if measure and j['build_tool']=='maven' else folder/'repo'/j['module']
 if j['build_tool']=='gradle':reports=list((folder/'recipes/measure/evidence/pit-native').rglob('mutations.csv'))
 else:reports=list((module/'target/pit-reports').rglob('mutations.csv'))
 selected_test=d.get('selected_test_fqcn') or d.get('actual_focal_fqcn','')+'_ESTest'
 if selected_test=='_ESTest':selected_test=('/'+j['focal_path'].lstrip('/')).split('/src/main/java/')[-1].removesuffix('.java').replace('/','.')+'_ESTest'
 package=selected_test.removesuffix('_ESTest').rpartition('.')[0]
 allrows=[]
 if len(reports)==1:
  with reports[0].open(encoding='utf-8-sig',newline='') as f:allrows=list(csv.reader(f))
 format_ok=bool(len(reports)==1 and all(len(r)==7 for r in allrows))
 focal=[r for r in allrows if len(r)==7 and r[0].removesuffix('.java')==j['focal_class'] and r[1].rpartition('.')[0]==package]
 foreign=[r for r in allrows if len(r)==7 and r[5]=='KILLED' and selected_test not in r[6]]
 process_ok=bool(measure and measure[-1]['finished'] and measure[-1]['returncode']==0 and not measure[-1]['timeout'])
 score=round(100*sum(r[5]=='KILLED' for r in focal)/len(focal),2) if focal else None
 valid=bool(format_ok and focal and not foreign and process_ok)
 if valid:assert score==d.get('mutation_score_percent'),'Stored score differs from raw report'
 suites=d.get('surefire_suites',[]);cases=d.get('cases',[])
 test='PASS' if d.get('strict_suite_evidence') else 'FAIL' if any(int(x.get('errors',0))+int(x.get('failures',0)) for x in suites) else 'SKIPPED_OR_INCOMPLETE' if suites else 'NOT_EVIDENCED'
 # Existing output classes plus source identity and reports establish compilation,
 # not merely BUILD SUCCESS or the absence of a compiler diagnostic.
 testclass=module/'target/test-classes'/Path(*selected_test.split('.')).with_suffix('.class')
 compiled=bool(suites or testclass.is_file())
 prod=list((module/'target/classes').rglob(j['focal_class']+'.class')) if j['build_tool']=='maven' else list((module/'build/classes').rglob(j['focal_class']+'.class'))
 return {'raw':d,'commands':cmd,'generation':'COMPLETE_SUITE' if d.get('generation_success',d.get('archived_E1_generation_success',False)) else 'UNSUCCESSFUL','compile_production':'PASS_ARTIFACT' if prod else 'NOT_EVIDENCED','compile_test':'PASS_ARTIFACT_OR_XML' if compiled else 'NOT_EVIDENCED','test_execution':test,'PIT':'VALID_FOCAL_REPORT' if valid else 'ZERO_FOCAL_MUTANTS' if format_ok and process_ok and not focal else 'UNRESOLVED_OR_NOT_RUN','process_gate':d.get('legacy_process_build'),'observed_mutation_percent':score if valid else None,'raw_reports':[pin(p) for p in reports],'focal_mutants':len(focal),'killed_mutants':sum(r[5]=='KILLED' for r in focal),'PIT_status_counts':dict(Counter(r[5] for r in focal)),'PIT_process_complete':process_ok,'foreign_killing_tests':len(foreign),'jacoco_focal_evidence':bool(d.get('jacoco_focal_rows')),'suite_evidence_complete':bool(d.get('strict_suite_evidence')),'module':str(module),'selected_test_fqcn':selected_test}
def cluster(values):
 if not values:return None
 repos=sorted({r[0] for r in values});s=np.array([sum(v for k,v in values if k==r) for r in repos]);n=np.array([sum(k==r for k,v in values) for r in repos]);rng=np.random.default_rng(20261023);draw=rng.integers(0,len(repos),(20000,len(repos)));stat=s[draw].sum(axis=1)/n[draw].sum(axis=1)
 return {'mean':float(s.sum()/n.sum()),'cluster_percentile_CI95':np.percentile(stat,[2.5,97.5]).tolist(),'n':len(values),'repositories':len(repos),'resamples':20000,'seed':20261023,'unit':'whole_repository_resampled; class_weighted_mean'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',default='analysis_v1');args=p.parse_args();out=A/args.output;assert not out.exists();out.mkdir()
 guards(load(R/'admission_maven_v6.json'));verify_pins(load(A/'input_audit/baseline_pins.json'))
 census=load(A/'input_audit/class_census300.json');jobs=load(R/'manifest300.json');oldhistory=load(R/'policy_attempt_history_v2/selection_current.json');rows=[];attempts=[];rawpins={}
 for j,c,history in zip(jobs,census,oldhistory):
  i=j['sample_index_1based'];assert c['class_key']==history['class_key']==j['class_key'];old=c['previous_E1'];selected=Path(old['E1_result_path']) if old.get('E1_result_path') else None
  amendment=None
  original_gradle=R/'jobs'/f'{i:03d}_gradle_v1'
  if original_gradle.exists():attempts.append({'index':i,'class_key':j['class_key'],'phase':'original_gradle_frozen_v1','folder':str(original_gradle),'commands':commands(original_gradle),'result':pin(original_gradle/'result.json') if (original_gradle/'result.json').exists() else None,'selection':'original frozen one-pass policy; not overwritten'})
  for group,version in [('pit','v2'),('pom','v1'),('pom','v2'),('junit3','v2')]:
   folder=R/'jobs'/f'{i:03d}_completion_{group}_{version}'
   if folder.exists():
    if (folder/'result.json').exists():selected=folder/'result.json';amendment=group
    attempts.append({'index':i,'class_key':j['class_key'],'phase':'post_outcome_'+group,'folder':str(folder),'commands':commands(folder),'result':pin(folder/'result.json') if (folder/'result.json').exists() else None,'unresolved':load(folder/'unresolved.json') if (folder/'unresolved.json').exists() else None,'selection':'single frozen attempt; no max-score selection','new_generation_allowed':group=='pom','test_edit_allowed':False})
  # Preserve the pre-spawn dispatcher failure as an attempt with zero starts.
  pre=R/'jobs'/f'{i:03d}_completion_pit_v1'
  if pre.exists():attempts.append({'index':i,'class_key':j['class_key'],'phase':'pre_spawn_dispatcher_failure','folder':str(pre),'commands':commands(pre),'selected':False,'reason':'UI path rejected before Gradle spawn'})
  row={'index':i,'class_key':j['class_key'],'repo_id':j['repo_id'],'build_tool':j['build_tool'],'commit_sha':j['commit_sha'],'seed':j['seed'],'fixed49':old['fixed_historical49'],'G0_build':old['G0_build'],'G0_strict':old['G0_strict'],'E0_build':old['E0_build'],'E0_strict':old['E0_strict'],'previous_E1_gate':old['E1_build'],'previous_E1_strict':old['E1_strict'],'previous_result':old.get('E1_result_path'),'new_amendment_group':amendment,'selected_result':pin(selected) if selected and selected.exists() else None,'historical_policy_selection':history,'review_groups':c['groups']}
  if selected and selected.exists():
   ev=evidence(j,selected);raw=ev.pop('raw');cmd=ev.pop('commands');row.update(ev);row['selected_legacy_strict']=raw['legacy_strict_mutation_percent'];row['end_to_end_score_percent']=None;row['score_basis']='UNRESOLVED'
   if raw.get('test_only_process_gate') is not None:
    row['test_only_process_gate']=raw['test_only_process_gate'];row['process_gate']=None;row['selected_legacy_strict']=None;row['PIT']='UNRESOLVED_PROVIDER_NOT_QUALIFIED'
   if row['PIT']=='VALID_FOCAL_REPORT' and row['process_gate']==1:row['end_to_end_score_percent']=row['observed_mutation_percent'];row['score_basis']='OBSERVED_PIT_AND_PROCESS_GATE'
   elif row['process_gate']==0 and 'GRADLE_TASK_REGISTRATION' not in c['groups']:
    # Preserve the historical end-to-end failure convention. This is NOT observed mutation 0%.
    actual_generation=any(x['kind']=='generation' and x['started'] for x in cmd)
    actual_measurement=any(x['kind'] in {'mutation_measurement','test_execution'} and x['started'] for x in cmd)
    if actual_generation or actual_measurement:row['end_to_end_score_percent']=0.0;row['score_basis']='CONVENTIONAL_END_TO_END_PIPELINE_FAILURE_ZERO_NOT_OBSERVED_MUTATION'
   if 'GRADLE_TASK_REGISTRATION' in c['groups']:
    row['score_basis']='UNRESOLVED_ADAPTER_TASK_BEFORE_GENERATION';row['generation']='NOT_STARTED_ADAPTER_BLOCK';row['process_gate_interpretation']='raw legacy 0 retained; not evidence of generated-suite build failure'
   if row['PIT']=='ZERO_FOCAL_MUTANTS':row['score_basis']='UNDEFINED_ZERO_FOCAL_MUTANTS_NO_PRIMARY_ZERO_FILL'
   if raw.get('test_only_process_gate') is not None:row['score_basis']='UNRESOLVED_PIT; TEST_ONLY_LIFECYCLE_REPORTED_SEPARATELY'
   row['measurement_flags']={'missing_JaCoCo_focal_row':not row['jacoco_focal_evidence'],'suite_incomplete_or_skipped':not row['suite_evidence_complete']}
   for x in row['raw_reports']:rawpins[x['path']]=x['sha256']
   rawpins[str(selected)]=sha(selected)
  else:
   row.update(generation='COMPLETE_SUITE_UNMEASURED' if any(g in c['groups'] for g in ['JUNIT3_SUPPORT','PIT_TOOL_RESOLUTION']) else 'NOT_STARTED_INPUT_BLOCK',compile_production='SEE_PRIOR_EVIDENCE',compile_test='NOT_EVIDENCED',test_execution='NOT_EVIDENCED',PIT='NOT_RUN',process_gate=None,observed_mutation_percent=None,end_to_end_score_percent=None,score_basis='UNRESOLVED_NO_ZERO_FILL',selected_legacy_strict=None)
  row['evidence_aware_process_gate']=None if 'GRADLE_TASK_REGISTRATION' in c['groups'] else row['process_gate']
  row['unresolved']=row['end_to_end_score_percent'] is None;rows.append(row)
 assert len(rows)==len({r['class_key'] for r in rows})==300
 assert all(r['new_amendment_group'] is None for r in rows if r['previous_E1_gate'] is not None),'This amendment should not replace any previous selected terminal record'
 stats={'n':300,'new_PIT_group_completed':sum(r['new_amendment_group']=='pit' for r in rows),'new_Maven_POM_results':sum(r['new_amendment_group']=='pom' for r in rows),'new_JUnit3_test_only_results':sum(r['new_amendment_group']=='junit3' for r in rows),'post_outcome':True,'full300_complete':not any(r['unresolved'] for r in rows),'unresolved_indices':[r['index'] for r in rows if r['unresolved']],'G0_full300_mean':sum(r['G0_strict'] for r in rows)/300,'G0_build':sum(r['G0_build'] for r in rows),'E0_build':sum(r['E0_build'] for r in rows),'E1_legacy_gate_pass':sum(r['process_gate']==1 for r in rows),'E1_legacy_gate_fail':sum(r['process_gate']==0 for r in rows),'E1_legacy_gate_unknown':sum(r['process_gate'] is None for r in rows),'test_status_counts':dict(Counter(r['test_execution'] for r in rows)),'PIT_status_counts':dict(Counter(r['PIT'] for r in rows)),'score_basis_counts':dict(Counter(r['score_basis'] for r in rows))}
 known=[r for r in rows if not r['unresolved']];unknown=len(rows)-len(known)
 stats['evidence_aware_available_case']={'E1_mean':cluster([(r['repo_id'],r['end_to_end_score_percent']) for r in known]),'paired_G0_minus_E1':cluster([(r['repo_id'],r['G0_strict']-r['end_to_end_score_percent']) for r in known])}
 legacy=[r for r in rows if r['selected_legacy_strict'] is not None]
 stats['legacy_pipeline_sensitivity_available']={'E1_mean':cluster([(r['repo_id'],r['selected_legacy_strict']) for r in legacy]),'G0_minus_E1':cluster([(r['repo_id'],r['G0_strict']-r['selected_legacy_strict']) for r in legacy]),'note':'contains old adapter task failures as raw zero; sensitivity only'}
 fixed=[r for r in rows if r['fixed49']];assert len(fixed)==49 and all(r['new_amendment_group'] is None for r in fixed)
 initial3=load(R/'jobs/003/result.json')['legacy_strict_mutation_percent']
 stats['original_index3_sensitivity']={'initial_result_sha256':sha(R/'jobs/003/result.json'),'E1_mean_available':cluster([(r['repo_id'],initial3 if r['index']==3 else r['end_to_end_score_percent']) for r in known]),'G0_minus_E1_available':cluster([(r['repo_id'],r['G0_strict']-(initial3 if r['index']==3 else r['end_to_end_score_percent'])) for r in known]),'note':'restore original class3 outcome, no best-of'}
 stats['fixed49_unchanged']={'E1_mean':cluster([(r['repo_id'],r['previous_E1_strict']) for r in fixed]),'G0_minus_E1':cluster([(r['repo_id'],r['G0_strict']-r['previous_E1_strict']) for r in fixed])}
 total=sum(r['end_to_end_score_percent'] for r in known);g=sum(r['G0_strict'] for r in rows)
 stats['deterministic_full300_bounds']={'unknown':unknown,'E1_mean':[total/300,(total+100*unknown)/300],'G0_minus_E1':[(g-total-100*unknown)/300,(g-total)/300],'not_confidence_interval':True,'not_NI_evidence':True}
 for fill in [0,100]:stats['sensitivity_missing_fill_'+str(fill)]=cluster([(r['repo_id'],r['G0_strict']-(r['end_to_end_score_percent'] if not r['unresolved'] else fill)) for r in rows])
 stats['legacy_gate_pass_rate_cluster_CI_available']=cluster([(r['repo_id'],100*r['process_gate']) for r in rows if r['process_gate'] is not None])
 gate_known=[r for r in rows if r['evidence_aware_process_gate'] is not None];passes=sum(r['evidence_aware_process_gate'] for r in gate_known);gate_unknown=300-len(gate_known)
 stats['evidence_aware_process_gate']={'pass':passes,'observed_denominator':len(gate_known),'unknown':gate_unknown,'available_rate_CI':cluster([(r['repo_id'],100*r['evidence_aware_process_gate']) for r in gate_known]),'full300_rate_bounds_percent':[100*passes/300,100*(passes+gate_unknown)/300],'not_compile_test_success_rate':True}
 dump(out/'class_results300.json',rows);dump(out/'attempts_addendum.json',attempts);dump(out/'statistics.json',stats);dump(out/'raw_report_pins.json',rawpins)
 lines=['# E1 completion — evidence audit','',f"300 class_key duy nhất; {len(known)} strict scores có cơ sở theo policy, {unknown} unresolved. Không gọi E1-full300 hoàn chỉnh nếu unresolved > 0.",'','GPT/E0 và số liệu RQ1–RQ3 giữ nguyên. Fixed49 giữ membership và selected results cũ. Không chạy repeated subset. Các số mới là hậu kiểm sau quan sát lỗi, không prespecified.','', '## Kết quả','',f"Legacy process gate pass: {stats['E1_legacy_gate_pass']}; fail: {stats['E1_legacy_gate_fail']}; chưa có gate: {stats['E1_legacy_gate_unknown']}. Đây không phải số compile pass hoặc test pass.",'',f"Unresolved indices: {stats['unresolved_indices']}",'','Các CI bootstrap theo repository có trong statistics.json; bounds là giới hạn xác định, không phải CI. Zero-fill được báo riêng, không ghi đè null trong bảng chính.','', '## Chấm theo bằng chứng','', 'Observed mutation được tính lại từ raw PIT và kiểm đúng focal/suite, exit code, denominator. Thiếu dòng JaCoCo không tự làm mất report PIT; skipped test được đánh dấu riêng. Lỗi adapter thiếu task trước generation giữ unresolved. Failure zero là quy ước end-to-end có nhãn, không phải mutation 0% đo được.','', '## Giới hạn công bằng','', 'E1 nhận hỗ trợ môi trường sau review (native runtime, selector/provider và tool resolution có điều kiện); GPT dùng pipeline lịch sử. Giữ GPT nguyên trạng không chứng minh công bằng môi trường. Không suy tác động riêng của assertions; không dùng giao mới thay fixed49 hay mẫu GPT ban đầu.','', '## Bảng 300 class','', '| Index | Class key | Gen | Compile test | Test | PIT | Gate | Observed % | Strict % |','|---:|---|---|---|---|---|---:|---:|---:|']
 for r in rows:lines.append('| '+' | '.join(str(r.get(k,'')) for k in ['index','class_key','generation','compile_test','test_execution','PIT','process_gate','observed_mutation_percent','end_to_end_score_percent'])+' |')
 (out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 # Preserve a bounded private evidence bundle of raw PIT reports, no credentials/config secrets.
 for k,(source,h) in enumerate(sorted(rawpins.items())):
  p=Path(source);dest=out/'raw_reports'/f'{k:04d}_{p.name}';dest.parent.mkdir(exist_ok=True);shutil.copy2(p,dest);assert sha(dest)==h
 manifest=[{'relative':p.relative_to(out).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in out.rglob('*') if p.is_file()];dump(out/'MANIFEST.json',manifest)
 print(json.dumps(stats,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
