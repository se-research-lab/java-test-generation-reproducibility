"""Partial-cohort provenance inventory, not rescoring or a new RQ analysis.
Reads result/manifest anchors only; never hashes growing subject trees.
"""
import csv,json,sys,urllib.request
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

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

guards(load(R/'admission_maven_v6.json'))
jobs=load(R/'manifest300.json')
assert len(jobs)==300 and len({j['class_key'] for j in jobs})==300
rows=[]
anchors={}
for j in jobs:
    i=j['sample_index_1based']
    base=R/'jobs'/f'{i:03d}'
    selected=selected_result(i)
    junit=R/'runtime/non_junit4_deferrals_v1'/f'{i:03d}.json'
    pom=R/'runtime/pom_input_deferrals_v1'/f'{i:03d}.json'
    row={'index':i,'class_key':j['class_key'],'build_tool':j['build_tool'],'seed':j['seed'],
         'state':None,'legacy_process_build':None,'saved_strict_percent':None,'saved_raw_mutation_percent':None,
         'focal_mutants':None,'strict_suite_evidence':None,'strict_measurement_evidence':None,
         'result_sha256':None,'decision_receipt_sha256':None,'stage_note':None}
    assert j['seed']==20261023+i
    result=None
    if j['reused_result']:
        saved=j['reused_result']
        result=load(saved['result_path'])
        assert sha(saved['result_path'])==saved['result_sha256']
        assert sha(saved['artifact_manifest_path'])==saved['artifact_manifest_sha256']
        row.update(state='REUSED_E49',result_sha256=saved['result_sha256'],stage_note='accepted reused evidence; no new execution')
    elif junit.exists() or pom.exists():
        receipt=junit if junit.exists() else pom
        decision=load(receipt)
        assert decision['sample_index_1based']==i and decision['class_key']==j['class_key']
        assert decision['score'] is None
        if junit.exists():
            assert sha(base/'artifact_manifest.json')==decision['archive_sha256']
            assert sha(base/'interrupted.json')==decision['interruption_sha256']
            assert sha(base/'before_dependency.json')==decision['dependency_evidence_sha256']
            assert decision['measurement_attempted'] is False
            for f in decision['native_suite']:assert sha(f['path'])==f['sha256']
            state='UNSCORED_NATIVE_JUNIT3'
        else:
            state='UNSCORED_FROZEN_POM'
        assert not (base/'result.json').exists()
        row.update(state=state,decision_receipt_sha256=sha(receipt),stage_note='retain fixed300 membership; no assigned score')
        anchors[str(i)]={'decision_path':receipt.relative_to(R).as_posix(),'decision_sha256':sha(receipt)}
    elif (base/'interrupted.json').exists():
        row.update(state='OTHER_INTERRUPTION_UNSCORED',stage_note='requires separate reconciliation; no accepted score')
    elif selected.exists():
        manifest=selected.parent/'artifact_manifest.json'
        if manifest.exists():
            entries=load(manifest)
            entry=next(x for x in entries if x['relative']==selected.name)
            assert entry['sha256']==sha(selected)
            anchors[str(i)]={'selected_result':selected.relative_to(R).as_posix(),'result_sha256':sha(selected),
                             'archive_manifest_sha256':sha(manifest),'full_byte_census_repeated':False}
        elif i==66:
            recovered=load(R/'audit/absent_v4_runner_reconciliation_v1/result.json')
            assert recovered['original_result_sha256']==sha(selected)
            assert sha(R/recovered['external_archive_path'])==recovered['external_archive_sha256']
            anchors[str(i)]={'selected_result':selected.relative_to(R).as_posix(),'result_sha256':sha(selected),
                             'external_archive_sha256':recovered['external_archive_sha256'],'full_byte_census_repeated':False}
        else:
            row.update(state='OPEN_RESULT_NOT_YET_ARCHIVED',stage_note='live write; not counted as accepted or zero-filled')
        if row['state'] is None:
            result=load(selected)
            assert result['source_guard']=='PASS' and result['production_bytecode_guard']=='PASS' and result['GPT_API_calls']==0
            base_result=load(base/'result.json')
            assert base_result['seed']==j['seed'] and base_result['class_key']==j['class_key']
            row.update(state='NEW_MAVEN_ARCHIVED_TERMINAL',result_sha256=sha(selected))
            if not base_result['generation_success']:
                row['stage_note']='generation stage unsuccessful; preserve actual terminal pipeline outcome'
            elif result['legacy_process_build']==0:
                row['stage_note']='measurement/build pipeline unsuccessful; preserve saved result'
            elif not result['strict_measurement_evidence']:
                row['stage_note']='process build gate true with measurement-evidence limitation; no metric change'
            else:
                row['stage_note']='saved focal mutation evidence; no new RQ inference'
    elif base.exists():
        row.update(state='IN_PROGRESS_OR_PREPARING_UNSCORED',stage_note='no terminal result; no zero-fill')
    else:
        row.update(state='GRADLE_NOT_ATTEMPTED' if j['build_tool']=='gradle' else 'MAVEN_NOT_ATTEMPTED',
                   stage_note='no execution or assigned score')
    if result is not None:
        assert result['class_key']==j['class_key'] if 'class_key' in result else i==3
        assert 0<=result['killed_mutants']<=result['focal_mutants']
        assert result['legacy_strict_mutation_percent']==(result['mutation_score_percent'] if result['legacy_process_build'] and result['mutation_score_percent'] is not None else 0.0)
        row.update(legacy_process_build=result['legacy_process_build'],saved_strict_percent=result['legacy_strict_mutation_percent'],
                   saved_raw_mutation_percent=result['mutation_score_percent'],focal_mutants=result['focal_mutants'],
                   strict_suite_evidence=result['strict_suite_evidence'],strict_measurement_evidence=result['strict_measurement_evidence'])
    rows.append(row)

counts=dict(Counter(r['state'] for r in rows))
assert sum(counts.values())==300 and counts['REUSED_E49']==49
assert counts.get('GRADLE_NOT_ATTEMPTED')==40
unscored=[r['index'] for r in rows if r['state'].startswith('UNSCORED_')]
with urllib.request.urlopen('http://127.0.0.1:8766/status.json',timeout=5) as response:status=json.load(response)
assert status['new_API_calls']==0 and status['runner_liveness'] in {'PRESENT_MATCHED_PID_AND_CREATE_TIME','INVOCATION_COMPLETION_RECORD_PRESENT'}
queue=load(R/'runtime/gradle_native_after_v6_v1/state.json')
assert queue['state']=='WAITING_FOR_CURRENT153_CLEAN_COMPLETION'
assert queue['new_EvoSuite_calls']==queue['GPT_API_calls']==0
assert not (R/'validation/gradle_native_runtime_fixture_v1').exists()
at=datetime.now(timezone.utc)
record={'status':'PASS_FIXED300_PARTIAL_METADATA_AND_RECEIPT_INVENTORY','at_utc':at.isoformat(),'class_state_counts':counts,
        'all300_unique_class_keys_and_original_seeds':'PASS','new_score_computation':False,'new_RQ_test':False,
        'unscored_indices':unscored,'result_and_receipt_anchors':anchors,
        'full_archive_byte_census_repeated':False,'not_a_transactional_snapshot':True,
        'runtime_observation':status,'post_Maven_single_synthetic_fixture_queue':queue,
        'new_Gradle_Java_processes':0,'new_GPT_API_calls':0,'paper_modified':False,'full300_complete':False}
dump(R/'audit/progress_v15.json',record)
with (R/'audit/partial300_inventory_v15.csv').open('x',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
table='\n'.join(f'|{name}|{count}|' for name,count in sorted(counts.items()))
local=at.astimezone(ZoneInfo('Asia/Bangkok')).strftime('%d/%m/%Y %H:%M:%S')
text=f'''# B1 — kiểm danh mục300 và chuẩn bị bước Gradle kế tiếp

Cập nhật **{local} (UTC+7)**. Runtime:`{status['phase']}`, active:`{status.get('active_sample_index')}`, owner:`{status['runner_liveness']}`. Preview hiện có{49+status['new_completed']} terminal records gồm49 E49. Batch Maven tiếp tục theo invocation v6 đã khóa; không restart hoặc đổi cấu hình.

## Kiểm danh mục, không tính lại kết quả

Đã đọc đủ300 class keys/seed gốc; kiểm result hash với archive manifest đã đóng, receipt của các class chưa chấm và bounds của trường điểm đã lưu.066 dùng recovered-archive đã xác minh;003 dùng measurement-only map đã khóa. Đây là kiểm metadata/anchors, không phải full byte census khác hoặc remeasurement. Class có result nhưng archive đang ghi chưa được tính accepted trong inventory.

|Trạng thái tại lúc đọc file|Số class|
|---|---:|
{table}

Snapshot nhiều file không mang tính giao dịch: runner có thể hoàn tất một class trong khi inventory đang đọc. `partial300_inventory_v15.csv` giữ đủ300 dòng, các trường điểm của class chưa chạy/chưa chấm để trống; không gán0, đổi denominator hoặc lấy E0 lấp E1. Điểm saved-strict và raw-mutant fields chỉ được chép nguyên từ policy/result cũ, không tạo thangP/C hoặc một cách kết luận RQ mới.

Các receipt mới vẫn cùng điều kiện JUnit3 compile scope đã khóa; tổng số chưa chấm lúc inventory:{len(unscored)}. Danh sách:`{unscored}`. Native suite/interruption/dependency/archive anchors khớp; chưa có measurement/result của nhóm này. Không regenerate hoặc nâng dependency production.10 class POM lỗi frozen input cũng giữ nguyên chưa chấm.

## Bước nối tiếp Gradle đã được khóa

Đã chuẩn bị queue mới riêng `queue_gradle_native_after_v6_v1.py`;18 kiểm tra thuần PASS. Queue đang **chờ** đúng completion hash của invocation153 hiện tại; chưa chạy fixture hoặc Gradle JVM.

Chỉ khi completion thật exit0, đã đi hết153 job của invocation, số scored/deferred khớp tổng211 new-Maven, không có error/API và dispatcher đã nhả khóa thì mở **một fixture Gradle2.13 tổng hợp** bằng native suite lưu sẵn. Fixture không sinh test hoặc cộng dòng vào300. Worker fixture có mutex riêng, offline cache riêng, artifact/source/bytecode/provider/report guards; fail hoặc lock busy thì dừng, không retry.

Đây là qualification của một component trong lúc benchmark idle, **không khẳng định Maven260/full300 đã thành công**: các class chưa chấm vẫn còn. Không tự admit Gradle40, không thêm GPT/API, không sửa paper. Các queue cũ đã SKIPPED được giữ nguyên, không restart. Nếu V6 dừng lỗi, queue mới cũng bỏ qua; không tự phục hồi batch.

Queue chỉ chờ ở process Python nhẹ; không chạy build/fixture Java đồng thời Maven. Toàn bộ source/pins/plan/stdout-stderr/state được giữ ở `runtime/gradle_native_after_v6_v1` và `runtime/gradle_after_v6_process_launch_v1`.

## Phần còn lại và ràng buộc

1. Hoàn tất hoặc khép an toàn phần Maven độc lập của V6. Giữ mọi terminal failure, seed/budget/parser cũ và disk guard12GB.
2. Review riêng các lớp JUnit3 và POM input chưa hỗ trợ. Không tự sửa classpath/compiler/provider hoặc chuẩn hóa POM để bảo toàn thứ hạng paper. Chưa có amendment repair được mở ở bước này.
3. Sau fixture Gradle2.13, cần các wrapper khác, native provider trên framework thực, target/budget mapping và generation adapter trước khi admit40. PASS của launcher hoặc fixture tổng hợp không tự thay bằng chứng corpus.
4. Audit toàn cohort và analytic cuối trước khi sửa paper/response. Giữ E0 lịch sử300, E1 bổ sung/fixed49/giao mới tách rõ; GPT61/45/300 và5RQ không đổi. Không NI300 từ cohort đang dở; R2.1/margin/equal budgets/hybrid và repeated evaluation chưa được đánh fully resolved nếu thiếu bằng chứng.

585 file gốc/backup, audit chain, GPT/E49/code-input guards PASS trong lần kiểm này. GPT/API0, repeated subset dừng, paper15 trang giữ nguyên. Chưa công khai code, artifact URL, upload, đăng ký, thanh toán hoặc ký license.

## File và preview

- [Preview local](http://127.0.0.1:8766/?view=b1-v2): chỉ đọc, trạng thái có thể tiến triển sau khi ghi report.
- `audit/progress_v15.json`, `audit/partial300_inventory_v15.csv`, `audit/progress_registry_v15.json`.
- `validation/gradle_fixture_after_v6_v1/result.json`, `runtime/gradle_native_after_v6_v1/plan.json`, `state.json`.
- `admission_maven_v6.json`, `launch_remaining_maven153_v6.json`; completion thật sẽ ở `runtime/remaining_maven153_v6_completion.json`.
'''
with (R/'PROGRESS_B1_V15.md').open('x',encoding='utf-8') as f:f.write(text)
paths=[Path(__file__),R/'PROGRESS_B1_V15.md',R/'audit/progress_v15.json',R/'audit/partial300_inventory_v15.csv',
       R/'src/prepare_gradle_fixture_after_v6_v1.py',R/'src/queue_gradle_native_after_v6_v1.py',
       R/'validation/gradle_fixture_after_v6_v1/result.json',R/'runtime/gradle_native_after_v6_v1/plan.json',
       R/'runtime/gradle_after_v6_process_launch_v1/plan.json',R/'runtime/gradle_after_v6_process_launch_v1/started.json',
       R/'admission_maven_v6.json',R/'launch_remaining_maven153_v6.json']
paths+=list((R/'runtime/non_junit4_deferrals_v1').glob('*.json'))
dump(R/'audit/progress_registry_v15.json',{'files':[{'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}
                                              for p in sorted(set(paths))]})
audit.log('B1_PROGRESS_V15_FIXED300_INVENTORY_AND_DEPENDENT_COMPONENT_SEALED',
          registry_sha256=sha(R/'audit/progress_registry_v15.json'),class_state_counts=counts,
          partial_unscored=len(unscored),new_Gradle_JVMs=0,new_GPT_API_calls=0,paper_modified=False)
print(json.dumps({'status':record['status'],'counts':counts,'observed_active':status.get('active_sample_index'),
                  'single_Gradle_component_queue':queue['state'],'new_Gradle_JVMs':0,'GPT_API_calls':0},indent=2))
