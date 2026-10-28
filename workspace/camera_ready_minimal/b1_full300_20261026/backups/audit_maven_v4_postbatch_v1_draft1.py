"""Offline verification of a stopped Maven invocation; never starts a tool.

Called only while its caller owns dispatcher.lock after a matching completion.
Writes a separate partial-cohort inventory; no manuscript or raw job is edited.
"""
import csv, importlib.util, json, sys, traceback
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from maven_adapter_v1 import R, sha, dump, checked_generation_argv
from checkpoint_archive_guard_v2 import verify
from measurement_parser_v1 import parse
from run_maven_b1_v3 import selected_result, counters
from non_junit4_deferral_v1 import inspect, REGISTRY
from classpath_transport_v1 import inflate

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit
OUT=R/'audit/maven_v4_postbatch_v1'

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def now():
    return datetime.now(timezone.utc).isoformat()

def integrity_checks(lock):
    # Experiment admission also enforces STOP and disk reserve. An offline
    # audit uses the immutable-input checks directly so a full disk/failed
    # invocation can still be diagnosed without admitting another experiment.
    audit.verify()
    checked=0
    for p,h in {**lock['code_and_input_hashes'],**lock['tool_hashes']}.items():
        assert sha(p)==h, 'Admitted code/input/tool drift: '+p
        checked+=1
    for row in load(R/'audit/input_lock.json'):
        assert sha(row['path'])==row['sha256'], 'Original B1 input drift'
        checked+=1
    path=R.parents[1]/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py'
    spec=importlib.util.spec_from_file_location('b1postbatch_gpt_guard',path)
    guard=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    assert guard.collect()==load(guard.LOCK), 'GPT frozen data drift'
    for name in ['measurement49_camera_ready_registry_v1.json','camera_ready_response_registry_v1.json','disclosure_only_registry_v1.json']:
        for row in load(B/'audit'/name)['files']:
            assert sha(B/row['path'])==row['sha256'], 'Accepted E49/paper evidence drift'
            checked+=1
    return {'status':'PASS','additional_pinned_files_checked':checked,'GPT':'PASS','original585_and_backups':'PASS','E49_and_paper_registries':'PASS'}

def generation_checks(folder,job):
    rows=[]
    for p in sorted((folder/'commands').glob('*/plan.json')):
        plan=load(p)
        argv=plan['argv']
        if '-jar' not in argv:
            continue
        ticket=folder/'command_admissions'/(p.parent.name+'.json')
        transport=load(ticket).get('transport_manifest') if ticket.exists() else None
        logical=inflate(argv,load(transport),folder) if transport else list(argv)
        assert logical[-2:]==['-seed',str(job['seed'])], 'Original seed changed'
        assert checked_generation_argv(logical[:-2],job,folder)==logical, 'Profile/target/argv changed'
        assert plan['timeout_seconds']==240, 'Generation timeout changed'
        for value,h in plan.get('input_hashes',{}).items():
            assert sha(value)==h, 'Pinned process input drift'
        started=(p.parent/'started.json').exists()
        assert not started or (p.parent/'finished.json').exists(), 'Generation process lacks finished evidence'
        rows.append({'plan':p.relative_to(R).as_posix(),'started':started,
                     'plan_sha256':sha(p),'CP_file_transport':bool(transport),'seed':job['seed']})
    assert len(rows)<=2, 'More than the locked conditional two attempts'
    return rows

def verify_reuse(job):
    saved=job['reused_result']
    result_path=Path(saved['result_path'])
    manifest_path=Path(saved['artifact_manifest_path'])
    assert result_path.resolve().is_relative_to(B) and manifest_path.resolve().is_relative_to(B)
    assert sha(result_path)==saved['result_sha256']
    assert sha(manifest_path)==saved['artifact_manifest_sha256']
    entries=load(manifest_path)
    for row in entries:
        path=(B/row['path']).resolve()
        assert path.is_relative_to(B) and sha(path)==row['sha256'], 'Reused E49 evidence drift'
    r=load(result_path)
    assert r['class_key']==job['class_key'] and r['seed']==job['seed']
    return r, {'status':'PASS','result_path':str(result_path),'result_sha256':sha(result_path),
               'archive_sha256':sha(manifest_path),'verified_evidence_files':len(entries)}

def score_fields(r):
    return {'legacy_process_build':r['legacy_process_build'],
            'legacy_strict_mutation_percent':r['legacy_strict_mutation_percent'],
            'mutation_score_percent':r['mutation_score_percent'],
            'focal_mutants':r['focal_mutants'],'killed_mutants':r['killed_mutants'],
            'strict_suite_evidence':r['strict_suite_evidence'],
            'strict_measurement_evidence':r['strict_measurement_evidence']}

def evidence_note(r):
    if not r['legacy_process_build']:
        return 'ACTUAL_TERMINAL_PIPELINE_FAILURE_STRICT_POLICY_ZERO'
    if r['mutation_score_percent'] is None:
        return 'PROCESS_GATE_TRUE_WITHOUT_FOCAL_MUTATION_PERCENTAGE'
    if not r['strict_measurement_evidence']:
        return 'POLICY_SCORE_RETAINED_EVIDENCE_LIMITATION'
    return 'OBSERVED_FOCAL_MUTATION_PERCENTAGE'

def run(completion,expected_plan_hash):
    assert completion['launch_plan_sha256']==expected_plan_hash
    assert not OUT.exists(), 'No overwrite or repeated post-batch audit'
    OUT.mkdir(parents=True,exist_ok=False)
    errors=[]
    rows=[]
    verification={}
    lock=load(R/'admission_maven_v4.json')
    context={j['sample_index_1based']:j for j in load(R/'inputs/context251_v1/manifest.json')}
    jobs=load(R/'manifest300.json')
    assert len(jobs)==300 and len({j['class_key'] for j in jobs})==300
    assert [j['sample_index_1based'] for j in jobs]==list(range(1,301))
    assert all(j['seed']==20261023+j['sample_index_1based'] for j in jobs)
    dump(OUT/'input_receipt.json',{'started_utc':now(),'completion':completion,
         'completion_sha256':sha(R/'runtime/remaining_maven183_v4_completion.json'),
         'expected_launch_plan_sha256':expected_plan_hash,'admission_sha256':sha(R/'admission_maven_v4.json'),
         'scope':'offline evidence verification only; no Java/API/experiments or comparative inference',
         'GPT_API_calls':0,'new_EvoSuite_calls':0,'paper_edits':0})
    try:
        integrity=integrity_checks(lock)
    except BaseException as ex:
        integrity={'status':'FAIL','type':type(ex).__name__,'detail':str(ex)}
        errors.append({'stage':'immutable_input_guards',**integrity})
    # Do not interpret metrics after a protected-input failure.
    if integrity['status']=='PASS':
        for job in jobs:
            i=job['sample_index_1based']
            row={'sample_index_1based':i,'class_key':job['class_key'],'build_tool':job['build_tool'],
                 'seed':job['seed'],'E1_state':None,'result_path':None,'result_sha256':None,
                 'legacy_process_build':None,'legacy_strict_mutation_percent':None,
                 'mutation_score_percent':None,'focal_mutants':None,'killed_mutants':None,
                 'strict_suite_evidence':None,'strict_measurement_evidence':None,'evidence_note':None}
            try:
                if job['reused_result']:
                    result,checks=verify_reuse(job)
                    verification[str(i)]=checks
                    row.update(E1_state='REUSED_VERIFIED_E49',result_path=checks['result_path'],result_sha256=checks['result_sha256'],
                               **score_fields(result),evidence_note=evidence_note(result))
                elif job['build_tool']=='gradle':
                    assert not (R/'jobs'/f'{i:03d}').exists(), 'Unexpected Gradle benchmark output during Maven-only invocation'
                    row.update(E1_state='GRADLE_NOT_ATTEMPTED',evidence_note='NO_SCORE_NO_ZERO_FILL')
                else:
                    base=R/'jobs'/f'{i:03d}'
                    selected=selected_result(i)
                    if (base/'interrupted.json').exists() and not (REGISTRY/f'{i:03d}.json').exists():
                        verification[str(i)]={'archive':verify(base),'interruption':load(base/'interrupted.json')}
                        row.update(E1_state='INTERRUPTED_UNSCORED',evidence_note='REVIEW_REQUIRED_NO_ACCEPTED_SCORE')
                    elif (REGISTRY/f'{i:03d}.json').exists():
                        decision=inspect(base)
                        assert decision==load(REGISTRY/f'{i:03d}.json')
                        verification[str(i)]=decision
                        row.update(E1_state='DEFERRED_UNSCORED',evidence_note='COMPILE_SCOPE_JUNIT3_NO_MEASUREMENT')
                    elif selected.exists():
                        checks={'original_archive':verify(base)}
                        if selected.parent!=base:
                            checks['selected_archive']=verify(selected.parent)
                        result=load(selected)
                        metadata=load(base/'job_admission.json')['job']
                        assert metadata['class_key']==job['class_key'] and metadata['seed']==job['seed']
                        if i!=3:
                            assert result['class_key']==job['class_key'] and result['seed']==job['seed']
                        else:
                            override=next(x for x in load(R/'measurement_result_map_v2.json')['overrides'] if x['sample_index_1based']==3)
                            assert override['measurement_sha256']==sha(selected)
                            checks['measurement_only_override']=override
                        module=selected.parent/'repo'/job['module']
                        c=context[i]
                        parsed=parse(module,job['focal_class'],c['package'],c['selected_test_fqcn'],result['legacy_process_build'])
                        assert all(result.get(k)==v for k,v in parsed.items()), 'Parsed archived evidence differs from saved result'
                        assert result['GPT_API_calls']==0 and result['source_guard']=='PASS' and result['production_bytecode_guard']=='PASS'
                        generation_folder=base if i==3 else selected.parent
                        checks['generation_commands']=generation_checks(generation_folder,metadata)
                        checks['offline_reparse']='IDENTICAL_FOR_ALL_PARSER_FIELDS'
                        verification[str(i)]=checks
                        row.update(E1_state='NEW_MAVEN_VERIFIED_TERMINAL',result_path=selected.relative_to(R).as_posix(),
                                   result_sha256=sha(selected),**score_fields(result),evidence_note=evidence_note(result))
                    elif base.exists():
                        row.update(E1_state='INCOMPLETE_UNSCORED',evidence_note='REVIEW_REQUIRED_NO_ACCEPTED_SCORE')
                    else:
                        row.update(E1_state='MAVEN_NOT_ATTEMPTED',evidence_note='NO_SCORE_NO_ZERO_FILL')
            except BaseException as ex:
                errors.append({'sample_index_1based':i,'type':type(ex).__name__,'detail':str(ex),'traceback':traceback.format_exc()})
                row.update(E1_state='AUDIT_FAILED_UNSCORED',evidence_note='DO_NOT_USE_UNTIL_RECONCILED')
            rows.append(row)
    state_counts=dict(Counter(r['E1_state'] for r in rows))
    accepted=state_counts.get('NEW_MAVEN_VERIFIED_TERMINAL',0)
    reused=state_counts.get('REUSED_VERIFIED_E49',0)
    if not errors:
        assert len(rows)==300 and reused==49
        assert accepted==completion['new_policy_accepted'], 'Dispatcher accepted count differs from offline verification'
    planned,started,fixtures=counters()
    record={'finished_utc':now(),'status':'FAIL_REQUIRES_RECONCILIATION' if errors else 'PASS_EXISTING_EVIDENCE_PARTIAL_COHORT',
            'scope':'Maven invocation offline evidence audit; not E1-full300 completion or an RQ test',
            'fixed_target':300,'state_counts':state_counts,'verified_reuse49':reused,
            'verified_new_Maven_terminal':accepted,'verified_total':reused+accepted,
            'input_integrity':integrity,'error_count':len(errors),'errors':errors,
            'benchmark_EvoSuite_plans':planned,'benchmark_EvoSuite_process_starts':started,
            'synthetic_fixture_EvoSuite_process_starts':fixtures,'new_JVM_processes':0,'GPT_API_calls':0,
            'raw_results_modified':False,'paper_modified':False,'full300_complete':False,
            'Maven260_all_accepted':not errors and reused+accepted==260,
            'infer_NI300_or_replace_GPT_samples_allowed':False}
    dump(OUT/'result.json',record)
    dump(OUT/'archive_and_parser_checks.json',verification)
    if rows:
        with (OUT/'manifest300.csv').open('x',newline='',encoding='utf-8-sig') as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    table='\n'.join(f'| {name} | {count} |' for name,count in sorted(state_counts.items()))
    report=f'''# Audit sau invocation Maven v4

UTC: {record['finished_utc']}. Trạng thái audit: **{record['status']}**. Đã xác minh{reused+accepted}/300 class có kết quả, gồm{reused} E49 tái sử dụng và{accepted} Maven mới. E1-full300 chưa hoàn tất; không có kiểm định RQ/NI hoặc thay mẫu GPT trong bước này.

|Trạng thái trong manifest cố định|Số class|
|---|---:|
{table}

Giữ nguyên một policy điểm của E49. `legacy_strict_mutation_percent` chỉ được điền cho kết quả đã thực thi và được nghiệm thu; class chưa chạy, chưa measurement, interrupted hoặc audit fail không bị gán0. `mutation_score_percent` và các evidence flags giữ đúng ý nghĩa đã có trong parser, không tạo thang đo P/C hoặc cách tính trung bình thay thế.

Đã kiểm archive gốc và measurement override đã khóa, hash/profile/seed/timeout/CP-file của lệnh generation, đối chiếu mọi trường parser của kết quả Maven mới với suite/PIT/JaCoCo đã lưu.49 E1 cũ kiểm đúng result và artifact manifest đã khóa. Measurement-only override003 được giữ với quyết định hậu nghiệm trong map v2; không sinh lại hoặc chọn score lớn nhất.

Generation plans:{planned}; benchmark EvoSuite starts:{started}; synthetic fixture starts:{fixtures}. Đây không phải independent repeated-run sample. Audit này không chạy JVM, Maven, Gradle, EvoSuite hoặc API mới và không sửa raw jobs/paper. GPT61/45/300, E0, E49 và5RQ được bảo vệ bằng hash. Single-run và repeated evaluation chưa hoàn chỉnh vẫn là giới hạn.

Số lỗi audit:{len(errors)}. Xem `result.json` và `archive_and_parser_checks.json`; `manifest300.csv` giữ đủ300 dòng khi input guards PASS. Không dùng hàng audit fail hoặc class chưa chấm cho comparative inference. Cần giải quyết các class chưa chấm, qualify Gradle40 trong sandbox E riêng và nghiệm thu đầy đủ trước khi cập nhật paper/R2.1 toàn300. Không khởi động lại batch, GPT hoặc repeated subset từ auditor này.
'''
    with (OUT/'REPORT.md').open('x',encoding='utf-8') as f:
        f.write(report)
    files=[p for p in sorted(OUT.iterdir()) if p.is_file()]
    dump(OUT/'manifest.json',{'files':[{'path':p.relative_to(R).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files]})
    audit.log('B1_MAVEN_V4_OFFLINE_AUDIT_FINISHED',result_sha256=sha(OUT/'result.json'),
              manifest_sha256=sha(OUT/'manifest.json'),status=record['status'],verified_total=reused+accepted,
              errors=len(errors),new_JVM_processes=0,GPT_API_calls=0)
    return record
