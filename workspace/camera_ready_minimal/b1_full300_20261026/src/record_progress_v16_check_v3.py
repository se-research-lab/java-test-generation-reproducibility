"""Short read-only check near the end of Maven v6; no execution changes."""
import json,sys,time,urllib.request
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import psutil
from maven_adapter_v1 import R,sha,dump
from run_maven_b1_v2 import guards
from preview_runner_health_v2 import same_owner
from run_maven_b1_v3 import selected_result
from checkpoint_archive_guard_v2 import verify

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def stamp():return datetime.now(timezone.utc)
plan=load(R/'launch_remaining_maven153_v6.json')
identity=plan['runner_identity']
guards(load(R/'admission_maven_v6.json'))

def observe():
    p=psutil.Process(identity['pid'])
    scripts=[a for a in p.cmdline() if a.lower().endswith('.py')]
    assert same_owner(identity,p.create_time(),scripts,R/'src/run_remaining_maven153_v6.py')
    c=p.cpu_times()
    io=p.io_counters()
    children=[]
    for child in p.children(recursive=True):
        try:children.append({'pid':child.pid,'name':child.name(),'create_time':child.create_time()})
        except psutil.NoSuchProcess:pass
    with urllib.request.urlopen('http://127.0.0.1:8766/status.json',timeout=5) as response:s=json.load(response)
    return {'at_utc':stamp().isoformat(),'runner_PID_and_creation_match':True,'runner_CPU_seconds':c.user+c.system,
            'runner_IO':io._asdict(),'owned_children':children,'disk_free_bytes':psutil.disk_usage(str(R)).free,'runtime':s}

first=observe()
time.sleep(20)
second=observe()
delta={'runner_CPU_seconds':second['runner_CPU_seconds']-first['runner_CPU_seconds'],
       'read_operations':second['runner_IO']['read_count']-first['runner_IO']['read_count'],
       'write_operations':second['runner_IO']['write_count']-first['runner_IO']['write_count'],
       'runtime_completed_change':second['runtime']['new_completed']-first['runtime']['new_completed']}
jobs=load(R/'manifest300.json')
terminal=[];incomplete=[];not_created=[]
for j in jobs:
    i=j['sample_index_1based']
    if j['reused_result'] or j['build_tool']!='maven':continue
    base=R/'jobs'/f'{i:03d}'
    chosen=selected_result(i)
    if chosen.exists() and not (chosen.parent/'interrupted.json').exists():terminal.append(i)
    elif (R/'runtime/non_junit4_deferrals_v1'/f'{i:03d}.json').exists() or (R/'runtime/pom_input_deferrals_v1'/f'{i:03d}.json').exists():
        pass  # Reviewed unscored class, including a future POM with no job folder.
    elif not base.exists():not_created.append(i)
    elif not (base/'interrupted.json').exists():
        incomplete.append({'index':i,'source_restore_receipt':(base/'input_snapshot_manifest.json').exists(),
                           'job_admission_present':(base/'job_admission.json').exists(),
                           'command_plans':len(list((base/'commands').glob('*/plan.json'))),
                           'terminal_result_present':(base/'result.json').exists()})
receipts=[]
for path in sorted((R/'runtime/non_junit4_deferrals_v1').glob('*.json')):
    r=load(path);i=r['sample_index_1based'];base=R/'jobs'/f'{i:03d}'
    assert r['score'] is None and r['measurement_attempted'] is False
    assert not (base/'result.json').exists()
    assert sha(base/'artifact_manifest.json')==r['archive_sha256']
    assert sha(base/'interrupted.json')==r['interruption_sha256']
    assert sha(base/'before_dependency.json')==r['dependency_evidence_sha256']
    for native in r['native_suite']:assert sha(native['path'])==native['sha256']
    receipts.append({'index':i,'receipt_sha256':sha(path),'anchor_check':'PASS','scope':'receipt/manifest/native/dependency anchors only; no new full repo census'})
fixedPOM=load(R/'audit/pom_input_deferrals_v2/result.json')['unparseable_indices']
all_unscored=sorted([r['index'] for r in receipts]+fixedPOM)
assert len(all_unscored)==len(set(all_unscored))
assert not set(terminal)&set(all_unscored)
assert len(terminal)+len(all_unscored)+len(not_created)+len(incomplete)==211
queue=load(R/'runtime/gradle_native_after_v6_v1/state.json')
assert queue['state']=='WAITING_FOR_CURRENT153_CLEAN_COMPLETION'
assert not (R/'runtime/remaining_maven153_v6_completion.json').exists()
assert not (R/'validation/gradle_native_runtime_fixture_v1').exists()
small_spot=None
if terminal:
    latest=max(terminal);out=selected_result(latest).parent
    entries=load(out/'artifact_manifest.json')
    if len(entries)<1500 and sum(x['bytes'] for x in entries)<30_000_000:
        small_spot={'index':latest,'archive':verify(out),'scope':'one closed archive; not a cohort-wide byte audit'}
at=stamp();s=second['runtime']
record={'status':'PASS_LIVE_RUNNER_AND_PARTIAL_FIXED300_CHECK','at_utc':at.isoformat(),
        'observations':[first,second],'observed_change':delta,'new_Maven_terminal_records_seen':len(terminal),
        'total_terminal_records_with49':49+len(terminal),'remaining_Maven_without_job_folder':not_created,
        'incomplete_job_observations':incomplete,'unscored_indices':all_unscored,
        'native_JUnit_receipt_checks':receipts,'latest_closed_archive_spot_check':small_spot,
        'Gradle_component_queue_state':queue['state'],'new_Gradle_JVMs':0,'new_GPT_API_calls':0,
        'experiment_config_changed':False,'paper_changed':False,'full300_complete':False,
        'multi_file_read_is_transactional':False}
dump(R/'audit/progress_v16.json',record)
local=at.astimezone(ZoneInfo('Asia/Bangkok')).strftime('%d/%m/%Y %H:%M:%S')
text=f'''# B1 — kiểm tra cuối chặng Maven v6

Thời điểm kiểm tra: **{local} (UTC+7)**. Đọc file hiện thấy **{49+len(terminal)} terminal records**, gồm49 E49 tái sử dụng và{len(terminal)} Maven mới. Có{len(all_unscored)} class chưa chấm;40 Gradle chưa chạy. Đây là inventory/anchors và một spot-check archive nhỏ, chưa thay audit toàn cohort cuối.

## Runner có tiếp tục hoạt động không?

Hai mẫu cách nhau20s đều khớp PID/create-time/script v6. CPU runner tăng{delta['runner_CPU_seconds']:.3f}s, read operations tăng{delta['read_operations']}, write operations tăng{delta['write_operations']}; counter completed thay đổi{delta['runtime_completed_change']}. Phase lúc mẫu cuối:`{s['phase']}`, active:`{s.get('active_sample_index')}`, owner:`{s['runner_liveness']}`.

Job chưa đóng quan sát được:`{incomplete}`. Nếu chưa có restore receipt/job admission/command plan thì đang tạo sandbox từ snapshot; Java chưa xuất hiện và nhãn CHECKPOINT cũ chưa tự là bằng chứng treo. Source restoration không có generation/API và không được gán score. Không can thiệp tiến trình để ép qua giai đoạn này.

Những Maven chưa có job folder lúc đọc:`{not_created}`. Tổng new-Maven vẫn211 khi cộng terminal, unscored, thư mục đang mở và class chưa tạo. Runtime/source folders có thể tiến triển giữa hai lần đọc nên đây không phải snapshot giao dịch.

## Class chưa chấm và guard

Danh sách chưa chấm:`{all_unscored}`. Có{len(receipts)} receipt JUnit3 compile scope, gồm mới224/239, và10 POM lỗi đã kiểm từ frozen input. Receipt, interruption, archive-manifest, dependency và native-suite anchors khớp; chưa measurement/result cho các trường hợp JUnit3. Không regenerate, nâng JUnit hoặc sửa namespace POM ở bước này; giữ mẫu300, không gán0 và không dùng E0 lấp E1.

585 file gốc/backup, code/input pins, audit chain và GPT/E49 guards PASS trong lần kiểm này. Không khởi động lại batch, sửa config, chạm GPT/E0/E49 hoặc paper. Điểm thấp/failure thực của subject tiếp tục được giữ, không chọn outcome thuận lợi.

## Disk và bước Gradle chờ

Đĩa còn{second['disk_free_bytes']/1e9:.2f}GB tại mẫu cuối, reserve12GB giữ nguyên. Không xóa, di chuyển hoặc nén evidence để tiếp tục. Counter disk trên status là mẫu gần nhất, có thể khác dung lượng thực trong khi đang tạo sandbox.

Completion V6 chưa có; queue `gradle_native_after_v6_v1` vẫn `{queue['state']}`. Chưa có fixture Gradle JVM/benchmark40 mới. Sau exact clean153 completion và dispatcher unlock mới được chạy một fixture tổng hợp Gradle2.13 với suite đã lưu. Nếu parent fail, thiếu receipt hoặc guard không khớp thì bỏ qua/dừng, không retry. Qualification đó chưa đồng nghĩa Gradle40 hoặc full300 thành công.

## Điểm tiếp tục

1. Giữ V6 chạy đến completion hoặc guard stop; không mở invocation trùng. Nếu runner mất, đối chiếu owner/commands/ledger trước mọi phục hồi.
2. Sau khi Maven nhả lock, kiểm completion, archive/receipts và fixture result thực; không báo PASS chỉ vì đã mở queue.
3. Review riêng các class chưa chấm; đủ dữ liệu/audit mới analytic RQ4/RQ5 và cập nhật paper. Giữ GPT61/45/300, E0 lịch sử300, fixed49/giao E1 mới tách rõ và5RQ. Không NI300 hoặc fully-resolved R2.1 từ cohort đang dở.

GPT/API mới0; repeated evaluation vẫn chưa hoàn chỉnh, paper15 trang giữ nguyên. Không công khai code, đặt artifact URL, upload, đăng ký, thanh toán hoặc ký license.

[Preview local](http://127.0.0.1:8766/?view=b1-v2). Bằng chứng: `audit/progress_v16.json`, `audit/progress_registry_v16.json`; logs theo từng job và serialized ledger. Completion cần kiểm: `runtime/remaining_maven153_v6_completion.json`.
'''
with (R/'PROGRESS_B1_V16.md').open('x',encoding='utf-8') as f:f.write(text)
paths=[Path(__file__),R/'PROGRESS_B1_V16.md',R/'audit/progress_v16.json',R/'admission_maven_v6.json',
       R/'launch_remaining_maven153_v6.json',R/'runtime/gradle_native_after_v6_v1/plan.json']
paths+=list((R/'runtime/non_junit4_deferrals_v1').glob('*.json'))
dump(R/'audit/progress_registry_v16.json',{'files':[{'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}
                                              for p in sorted(set(paths))]})
audit.log('B1_PROGRESS_V16_LIVE_PARTIAL300_CHECKED',registry_sha256=sha(R/'audit/progress_registry_v16.json'),
          total_terminal=49+len(terminal),unscored=len(all_unscored),incomplete=incomplete,
          observed_change=delta,new_Gradle_JVMs=0,new_GPT_API_calls=0,experiment_changes=0)
print(json.dumps({'status':record['status'],'total_terminal':49+len(terminal),'unscored':len(all_unscored),
                  'incomplete':incomplete,'Maven_folders_not_created':len(not_created),'observed_change':delta,
                  'disk_free_GB':second['disk_free_bytes']/1e9,'Gradle_component_queue':queue['state'],
                  'GPT_API_calls':0},indent=2))
