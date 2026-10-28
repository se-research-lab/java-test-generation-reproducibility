"""Count unique subjects with native tests but unsuccessful process gate.
Offline result/log analysis only; no compiler/test/generator/API is executed.
"""
import csv,json,re,sys
from collections import Counter
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
from run_maven_b1_v2 import guards
from run_maven_b1_v3 import selected_result

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit
OUT=R/'audit/generated_test_build_failures_v1'

def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))

def completed_anchor(folder,result):
    manifest=folder/'artifact_manifest.json'
    if manifest.exists():
        rows=load(manifest)
        row=next(x for x in rows if x['relative']==result.name)
        assert row['sha256']==sha(result)
        return {'manifest_sha256':sha(manifest),'result_sha256':sha(result),
                'scope':'saved result and manifest anchor; not a full repeated repo census'}
    assert folder==R/'jobs/066'
    recovered=load(R/'audit/absent_v4_runner_reconciliation_v1/result.json')
    assert recovered['original_result_sha256']==sha(result)
    assert sha(R/recovered['external_archive_path'])==recovered['external_archive_sha256']
    return {'external_manifest_sha256':recovered['external_archive_sha256'],'result_sha256':sha(result)}

assert not OUT.exists(),'Preserve earlier analysis; never overwrite'
guards(load(R/'admission_maven_v6.json'))
completion=load(R/'runtime/remaining_maven153_v6_completion.json')
assert completion['exit_code']==0 and completion['jobs_finished_this_invocation']==153
assert completion['new_policy_accepted']==191 and completion['Maven_unattempted']==0
jobs=load(R/'manifest300.json')
assert len(jobs)==300 and len({j['class_key'] for j in jobs})==300
OUT.mkdir(parents=True,exist_ok=False)
counts=Counter();rows=[];failures=[];deferred=[];checks={};raw_logs={}
for j in jobs:
    i=j['sample_index_1based'];base=R/'jobs'/f'{i:03d}'
    row={'index':i,'class_key':j['class_key'],'repo_id':j['repo_id'],'focal_class':j['focal_class'],
         'scope':None,'generation_success':None,'native_suite_complete':None,'process_build_gate':None,
         'strict_suite_evidence':None,'strict_measurement_evidence':None,'category':None,
         'failure_kind':None,'result_path':None,'result_sha256':None,'native_files_sha256':None}
    native_receipt=R/'runtime/non_junit4_deferrals_v1'/f'{i:03d}.json'
    pom_receipt=R/'runtime/pom_input_deferrals_v1'/f'{i:03d}.json'
    if j['reused_result']:
        saved=j['reused_result'];p=Path(saved['result_path']);r=load(p)
        assert sha(p)==saved['result_sha256'] and sha(saved['artifact_manifest_path'])==saved['artifact_manifest_sha256']
        assert r['archived_E1_generation_success'] is True and r['legacy_process_build']==1
        row.update(scope='REUSED_E49',generation_success=True,native_suite_complete=True,
                   process_build_gate=1,strict_suite_evidence=r['strict_suite_evidence'],
                   strict_measurement_evidence=r['strict_measurement_evidence'],category='GENERATED_PROCESS_GATE_PASSED',
                   result_path=str(p),result_sha256=sha(p))
        counts['reuse49_generated_build_pass']+=1
    elif j['build_tool']=='gradle':
        assert not base.exists()
        row.update(scope='NEW_GRADLE40',category='GRADLE_NOT_ATTEMPTED')
        counts['Gradle_not_attempted']+=1
    elif native_receipt.exists():
        d=load(native_receipt)
        assert d['class_key']==j['class_key'] and d['score'] is None and d['measurement_attempted'] is False
        assert sha(base/'artifact_manifest.json')==d['archive_sha256']
        assert sha(base/'interrupted.json')==d['interruption_sha256']
        assert not (base/'result.json').exists() and len(d['native_suite'])==2
        for f in d['native_suite']:assert sha(f['path'])==f['sha256']
        row.update(scope='NEW_MAVEN',generation_success=True,native_suite_complete=True,
                   category='GENERATED_GUARD_STOPPED_BEFORE_MEASUREMENT',failure_kind='JUnit3_compile_scope_review_required',
                   native_files_sha256=';'.join(f['sha256'] for f in d['native_suite']))
        counts['generated_but_not_measured_JUnit_guard']+=1
        deferred.append(dict(row))
    elif pom_receipt.exists():
        d=load(pom_receipt)
        assert d['score'] is None and d['new_generation_calls']==0
        row.update(scope='NEW_MAVEN',generation_success=False,native_suite_complete=False,
                   category='FROZEN_POM_INPUT_UNSCORED_NO_GENERATION',failure_kind='unbound_XML_prefix')
        counts['POM_unscored_no_generation']+=1
    else:
        p=selected_result(i)
        assert p.exists() and not (p.parent/'interrupted.json').exists()
        r=load(p);original=load(base/'result.json')
        generation_folder=base if i==3 else p.parent
        native=load(generation_folder/'native_generated.json')
        generated=bool(original['generation_success'] if i==3 else r['generation_success'])
        assert bool(native['complete'])==generated
        assert original['class_key']==j['class_key'] and original['seed']==j['seed']
        assert r['source_guard']==r['production_bytecode_guard']=='PASS' and r['GPT_API_calls']==0
        for f in native['files']:assert sha(f['path'])==f['sha256']
        checks[str(i)]=completed_anchor(p.parent,p)
        row.update(scope='NEW_MAVEN',generation_success=generated,native_suite_complete=bool(native['complete']),
                   process_build_gate=r['legacy_process_build'],strict_suite_evidence=r['strict_suite_evidence'],
                   strict_measurement_evidence=r['strict_measurement_evidence'],result_path=p.relative_to(R).as_posix(),
                   result_sha256=sha(p),native_files_sha256=';'.join(f['sha256'] for f in native['files']))
        if not generated:
            assert not r['legacy_process_build']
            row.update(category='GENERATION_UNSUCCESSFUL')
            counts['generation_unsuccessful_terminal']+=1
        elif r['legacy_process_build']:
            row.update(category='GENERATED_PROCESS_GATE_PASSED')
            counts['new_generated_build_pass']+=1
        else:
            assert r['measurement_attempted'] is True
            evidence=[]
            for command in sorted((p.parent/'commands').glob('*/plan.json')):
                spec=load(command)
                if 'org.pitest:pitest-maven:mutationCoverage' not in spec['argv']:continue
                finish=load(command.parent/'finished.json')
                stdout=command.parent/'stdout.txt';stderr=command.parent/'stderr.txt'
                assert sha(stdout)==finish['stdout_sha256'] and sha(stderr)==finish['stderr_sha256']
                text=stdout.read_text(encoding='utf-8',errors='replace')+'\n'+stderr.read_text(encoding='utf-8',errors='replace')
                goals=[line.strip() for line in text.splitlines() if 'Failed to execute goal' in line]
                has_compilation_error='COMPILATION ERROR' in text
                if len(goals)==1 and 'license-maven-plugin:' in goals[0] and ':check-file-header' in goals[0] and 'file(s) with no header' in goals[0]:
                    kind='LICENSE_HEADER_PLUGIN'
                elif len(goals)==1 and 'org.pitest:pitest-maven:' in goals[0] and 'Coverage generation minion exited abnormally' in goals[0] and 'UNKNOWN_ERROR' in goals[0]:
                    kind='PIT_COVERAGE_MINION_UNKNOWN_ERROR'
                else:
                    kind='NEEDS_MANUAL_CLASSIFICATION'
                evidence.append({'command':command.parent.relative_to(R).as_posix(),'stdout_sha256':sha(stdout),
                     'stderr_sha256':sha(stderr),'returncode':finish['returncode'],'failure_kind':kind,
                     'failed_goal_lines':goals,'compilation_error_marker_present':has_compilation_error})
            assert len(evidence)==1 and evidence[0]['returncode']!=0
            assert evidence[0]['failure_kind']!='NEEDS_MANUAL_CLASSIFICATION'
            row.update(category='GENERATED_MEASUREMENT_PROCESS_GATE_FAILED',failure_kind=evidence[0]['failure_kind'])
            failures.append(dict(row));raw_logs[str(i)]=evidence[0]
            counts['generated_measurement_process_gate_failed']+=1
    rows.append(row)

assert len(rows)==300
assert counts==Counter({'reuse49_generated_build_pass':49,'new_generated_build_pass':146,
                        'generated_measurement_process_gate_failed':18,'generated_but_not_measured_JUnit_guard':10,
                        'generation_unsuccessful_terminal':27,'POM_unscored_no_generation':10,'Gradle_not_attempted':40})
failure_counts=dict(Counter(r['failure_kind'] for r in failures))
assert failure_counts=={'LICENSE_HEADER_PLUGIN':8,'PIT_COVERAGE_MINION_UNKNOWN_ERROR':10}
assert all(not e['compilation_error_marker_present'] for e in raw_logs.values())
assert sum(r['strict_suite_evidence'] is True for r in failures)==13
gate_true=[r for r in rows if r['process_build_gate']==1]
assert len(gate_true)==195
extra={'gate_true_but_suite_evidence_false':[r['index'] for r in gate_true if r['strict_suite_evidence'] is False],
       'gate_true_but_measurement_evidence_false':[r['index'] for r in gate_true if r['strict_measurement_evidence'] is False]}
fixture=load(R/'validation/gradle_native_runtime_fixture_v1/gradle_2.13/failure.json')
assert fixture['status']=='QUALIFICATION_FAILED_NO_BENCHMARK'
at=datetime.now(timezone.utc)
summary={'status':'PASS_UNIQUE_CLASS_GENERATION_BUILD_FAILURE_COUNT','at_utc':at.isoformat(),
         'scope':'E1 fixed300;49 reused+191 new terminal;10 generated deferred;10 POM deferred;40 Gradle not attempted',
         'groups':dict(counts),'generated_unique_classes_with_native_tests':223,
         'generated_and_process_gate_failed':18,'failure_kinds':failure_counts,
         'generated_but_not_measured_guard_stops':10,'generated_without_process_gate_success_including_unmeasured':28,
         'failed_process_group_with_passing_unit_suite':13,
         'compiler_error_markers_in_the18':0,'process_gate_true_total':195,'gate_true_evidence_limitations':extra,
         'completion_sha256':sha(R/'runtime/remaining_maven153_v6_completion.json'),
         'Gradle_fixture_failure_excluded_from_class_count':True,'full300_complete':False,
         'class_count_not_attempt_count':True,'metric_redefined':False,'raw_evidence_changed':False,
         'new_Java_or_EvoSuite_jobs':0,'new_GPT_API_calls':0,'paper_modified':False}
dump(OUT/'summary.json',summary)
dump(OUT/'result_anchors.json',checks)
dump(OUT/'failure_log_evidence.json',raw_logs)
for name,data in [('class_inventory300.csv',rows),('generated_failed18.csv',failures),('generated_unmeasured10.csv',deferred)]:
    with (OUT/name).open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
table='\n'.join(f"|{r['index']}|{r['focal_class']}|{'License header' if r['failure_kind']=='LICENSE_HEADER_PLUGIN' else 'PIT minion UNKNOWN_ERROR'}|{'pass' if r['strict_suite_evidence'] else 'chưa đủ bằng chứng pass'}|" for r in failures)
pending='\n'.join(f"|{r['index']}|{r['focal_class']}|JUnit3 compile scope; chưa measurement|" for r in deferred)
local=at.astimezone(ZoneInfo('Asia/Bangkok')).strftime('%d/%m/%Y %H:%M:%S')
report=f'''# Đếm class đã sinh test nhưng pipeline build/measurement thất bại

Kiểm tra **{local} (UTC+7)**. Câu trả lời theo process/build gate đang dùng trong protocol: **18 class đã sinh đủ native test + scaffolding nhưng measurement pipeline trả BUILD FAILURE/gate0**. Cả18 thuộc191 Maven mới;49 E1 tái sử dụng không có thêm trường hợp gate0.

**Không gọi đây là18 lỗi biên dịch Java.** Đối chiếu failed Maven goal và log cho thấy8 lỗi license-header plugin và10 lỗi PIT coverage minion `UNKNOWN_ERROR`. Không có marker `COMPILATION ERROR` trong nhóm18.13/18 còn có native suite pass trong report đã lưu; phần thất bại nằm ở bước pipeline khác. Đây không phải bằng chứng mọi test của5 class còn lại có thể compile/pass, vì plugin đã chặn lifecycle trước khi có đủ suite evidence.

## Cách đếm, tránh gộp sai

Đếm **class key duy nhất**, không cộng technical retries, recovery folders, generation attempts hoặc synthetic fixtures. Chọn đúng measurement map đã khóa:003 dùng measurement-only override,012/016/023 dùng recovery transport; không cộng kết quả cũ và mới hai lần. Generated thành công được đối chiếu `native_generated.complete` với generation flag và hash hai native source files. Các result hash đối chiếu artifact manifest hoặc archive phục hồi066; không full-rehash toàn repo ở bước này.

|Nhóm trong manifest300|Số class|
|---|---:|
|Đã sinh test, process build gate pass|195 (49 tái sử dụng +146 mới)|
|Đã sinh test, build/measurement gate thất bại thật|18|
|Đã sinh test nhưng guard dừng trước measurement, chưa có score|10|
|Generation không thành công, có terminal result|27|
|POM frozen input lỗi, chưa generation/chưa score|10|
|Gradle chưa benchmark|40|
|Tổng|300|

Như vậy có **223 class đã có native test**, trong đó195 gate pass,18 gate fail và10 chưa được đo. Nếu câu hỏi là “đã có test nhưng chưa có process-gate thành công” thì tổng là **28=18+10**; phải tách10 chưa thử measurement khỏi18 failure đã quan sát. Không được gọi cả28 là failed build.37 trường hợp27 generation failure +10 POM chưa generation cũng không thuộc nhóm đã sinh test thành công.

Process gate là policy cũ, không phải chứng nhận suite validity hoàn chỉnh. Trong195 gate pass có{len(extra['gate_true_but_suite_evidence_false'])} class chưa đủ suite evidence và{len(extra['gate_true_but_measurement_evidence_false'])} chưa đủ complete measurement evidence theo flags đã lưu. Chúng không được tự chuyển sang nhóm18 hoặc tạo thangP/C mới; cần disclosure/sensitivity riêng khi chốt analytic.

##18 class đã sinh test nhưng process gate fail

|Index gốc|Focal class|Failed stage|Native suite evidence|
|---|---|---|---|
{table}

Log kiểm theo đúng lệnh measurement `clean verify ... mutationCoverage`, không lấy một chuỗi lỗi từ generation rồi quy nhầm sang build. `failure_log_evidence.json` giữ path command, failed-goal lines, returncode và stdout/stderr hashes.

###8 license-header plugin failures

Index012/023/027/061/079/085/091/236. Log ghi generated test/scaffolding có file thiếu header và goal `license-maven-plugin:check-file-header` fail. Không tự sửa native source hoặc thêm skip flags để lấy một kết quả mới. Chưa biến lỗi này thành kết luận oracle yếu hoặc model sinh test sai.

###10 PIT minion failures

Index066/082/100/104/130/154/176/189/219/244, cùng repo61565876. Native suite đã pass; PIT coverage generation minion thoát `UNKNOWN_ERROR`, không có focal mutation report dùng được. Chưa đủ bằng chứng gán nguyên nhân sâu hơn cho JUnit/provider/EvoSuite hoặc code subject; cần diagnostic riêng, không tự nâng dependency/đổi JVM hoặc chạy lại subject.

##10 class đã có test nhưng chưa measurement

|Index gốc|Focal class|Trạng thái|
|---|---|---|
{pending}

Đây là10 class repo44308560 có JUnit3 trong production compile closure. Native test đã được lưu; compatibility guard dừng, không nâng dependency, không measurement và không gán0. Giữ trong mẫu300 và chưa đánh là actual build failure.

## Trạng thái batch và giới hạn paper

V6 đã kết thúc sạch exit0:145 terminal mới+8 deferral trong invocation153; cộng checkpoint trước thành191 Maven mới có terminal result. Với49 E49 tái sử dụng hiện có240 terminal records,20 chưa chấm và40 Gradle chưa benchmark. **E1-full300 chưa hoàn tất**.

Fixture tổng hợp Gradle2.13 đã chạy một lần sau Maven idle, lỗi ở `compile_classpath` vì không tìm thấy extension `sourceSets`; queue dừng và không retry. Fixture không thuộc300 class và không sinh EvoSuite mới, không cộng vào18 hay28. Chưa sửa fixture hoặc mở Gradle40 ở bước trả lời này.

Đây là analytic đọc raw result/log, không compile/test/generate lại. GPT/API0;585 file gốc/backup, audit chain và GPT/E49 guards PASS. Không sửa score, nguồn experiment gốc, paper15 trang hoặc5RQ; không công khai code, artifact URL, upload, thanh toán/đăng ký/ký license. Muốn sửa các lỗi integration phải có amendment scope và sandbox riêng, giữ nguyên log/kết quả ban đầu, không tune để bảo toàn kết luận.

File bàn giao: `summary.json`, `class_inventory300.csv`, `generated_failed18.csv`, `generated_unmeasured10.csv`, `failure_log_evidence.json`, `result_anchors.json`, `manifest.json`.
'''
with (OUT/'REPORT.md').open('x',encoding='utf-8') as f:f.write(report)
dump(OUT/'manifest.json',{'files':[{'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}
                                for p in sorted(OUT.iterdir()) if p.is_file()]})
audit.log('B1_GENERATED_TEST_BUILD_FAILURES_UNIQUE_CLASS_COUNTED',summary_sha256=sha(OUT/'summary.json'),
          manifest_sha256=sha(OUT/'manifest.json'),actual_generated_gate_failures=18,
          generated_guard_unmeasured=10,license_header=8,PIT_minion=10,new_Java_jobs=0,new_GPT_API_calls=0)
print(json.dumps(summary,indent=2))
