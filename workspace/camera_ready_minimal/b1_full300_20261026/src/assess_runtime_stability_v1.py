"""Observe live v6 twice; no experiment/configuration/process modification.
Writes only a new diagnostic report/receipt, no live source or status changes.
"""
import json,os,sys,time,urllib.request
from datetime import datetime,timezone
from pathlib import Path
import psutil
from maven_adapter_v1 import R,sha,dump
from preview_runner_health_v2 import same_owner
from prepare_sandbox_v1 import E49_EXCLUDED
from checkpoint_archive_guard_v2 import verify

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit
OUT=R/'audit/runtime_stability_v1'

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def now():
    return datetime.now(timezone.utc)

def snapshot(identity):
    at=now()
    proc=psutil.Process(identity['pid'])
    scripts=[s for s in proc.cmdline() if s.lower().endswith('.py')]
    owner=same_owner(identity,proc.create_time(),scripts,R/'src/run_remaining_maven153_v6.py')
    assert owner,'Owner PID/create-time/script mismatch; never treat stale snapshot as a live process'
    cpu=proc.cpu_times()
    io=proc.io_counters()
    processes=[]
    for child in [proc]+proc.children(recursive=True):
        try:
            mem=child.memory_info()
            times=child.cpu_times()
            processes.append({'pid':child.pid,'parent_pid':child.ppid(),'name':child.name(),
                 'create_time':child.create_time(),'CPU_seconds':times.user+times.system,'RSS_bytes':mem.rss,
                 'status':child.status()})
        except (psutil.NoSuchProcess,psutil.AccessDenied):
            continue
    with urllib.request.urlopen('http://127.0.0.1:8766/status.json',timeout=5) as response:
        state=json.load(response)
    memory=psutil.virtual_memory()
    return {'at_utc':at.isoformat(),'timestamp':at.timestamp(),'owner_identity_match':owner,
            'runner_CPU_seconds':cpu.user+cpu.system,'runner_IO':io._asdict(),'owned_process_tree':processes,
            'owned_RSS_sum_bytes':sum(p['RSS_bytes'] for p in processes),
            'host_memory_available_bytes':memory.available,'host_memory_total_bytes':memory.total,
            'host_memory_used_percent':memory.percent,'disk_free_bytes':psutil.disk_usage(str(R)).free,
            'runtime_status':state}

assert not OUT.exists(),'Use a new diagnostic version; preserve old observations'
plan=load(R/'launch_remaining_maven153_v6.json')
identity=plan['runner_identity']
assert plan['launcher_sha256']==sha(R/'src/run_remaining_maven153_v6.py')
assert plan['admission_sha256']==sha(R/'admission_maven_v6.json')
OUT.mkdir(parents=True,exist_ok=False)
first=snapshot(identity)
dump(OUT/'sample1.json',first)
time.sleep(20)
second=snapshot(identity)
dump(OUT/'sample2.json',second)
end=now()
elapsed=second['timestamp']-first['timestamp']
delta={'sample_interval_seconds':elapsed,'runner_CPU_seconds':second['runner_CPU_seconds']-first['runner_CPU_seconds'],
       'runner_IO_read_operations':second['runner_IO']['read_count']-first['runner_IO']['read_count'],
       'runner_IO_write_operations':second['runner_IO']['write_count']-first['runner_IO']['write_count'],
       'completed_jobs':second['runtime_status']['new_completed']-first['runtime_status']['new_completed'],
       'runtime_snapshot_changed':second['runtime_status']['updated_utc']!=first['runtime_status']['updated_utc']}

completed=[]
commands=[]
intervals=[]
last_progress=[]
pending=[]
read_races=[]
for i in plan['sample_indices']:
    folder=R/'jobs'/f'{i:03d}'
    if not folder.exists():
        pending.append(i)
        continue
    if (folder/'events.jsonl').exists():
        lines=(folder/'events.jsonl').read_text(encoding='utf-8').splitlines()
        try:
            event=json.loads(lines[-1])
            last_progress.append({'index':i,'last_kind':event['kind'],'at_utc':event['at_utc']})
        except (json.JSONDecodeError,IndexError):
            read_races.append({'index':i,'note':'last event may be being appended; not an experiment failure'})
    result=folder/'result.json'
    manifest=folder/'artifact_manifest.json'
    if result.exists() and manifest.exists() and not (folder/'interrupted.json').exists():
        r=load(result)
        admission=load(folder/'job_admission.json')
        completed.append({'index':i,'started_utc':admission['started_utc'],'result_sha256':sha(result),
             'legacy_process_build':r['legacy_process_build'],'generation_success':r['generation_success'],
             'measurement_attempted':r['measurement_attempted'],'strict_suite_evidence':r['strict_suite_evidence'],
             'strict_measurement_evidence':r['strict_measurement_evidence'],'GPT_API_calls':r['GPT_API_calls']})
    for p in sorted((folder/'commands').glob('*/plan.json')):
        started=p.parent/'started.json'
        if not started.exists():
            continue
        try:
            spec=load(p)
            begin=load(started)
            finished=p.parent/'finished.json'
            ending=load(finished) if finished.exists() else None
        except json.JSONDecodeError:
            read_races.append({'index':i,'command':p.parent.name,'note':'concurrent JSON write; omitted from this observation'})
            continue
        argv=spec['argv']
        kind='EvoSuite_generation' if '-jar' in argv else ('measurement' if 'org.pitest:pitest-maven:mutationCoverage' in argv else 'compile_or_dependency_audit')
        elapsed_current=(end-datetime.fromisoformat(begin['started_utc'])).total_seconds()
        row={'index':i,'command':p.parent.name,'stage':kind,'timeout_seconds':spec['timeout_seconds'],
             'started_utc':begin['started_utc'],'finished':ending is not None,
             'returncode':ending['returncode'] if ending else None,'termination_reason':ending.get('reason') if ending else None,
             'elapsed_seconds':ending['elapsed_seconds'] if ending else elapsed_current,
             'overdue_now':ending is None and elapsed_current>spec['timeout_seconds']+30}
        commands.append(row)
        start=datetime.fromisoformat(begin['started_utc']).timestamp()
        finish=datetime.fromisoformat(ending['finished_utc']).timestamp() if ending else end.timestamp()
        intervals.append((start,finish,i,p.parent.name))
overlaps=[]
ordered=sorted(intervals)
for a,b in zip(ordered,ordered[1:]):
    if a[1]>b[0]+.05:
        overlaps.append({'previous_index':a[2],'next_index':b[2],'overlap_seconds':a[1]-b[0]})
active=[c for c in commands if not c['finished']]
overdue=[c for c in active if c['overdue_now']]

# Estimate only the required source bytes for not-yet-materialized jobs. This
# excludes new build/report/cache/log bytes, so it is a lower bound, not an ETA.
index=load(R/'inputs/snapshot_v3/index.json')
lower_bound=0
capacity_rows=[]
for i in pending:
    m=next(x for x in index if i in x['class_indices'])
    path=R/m['manifest']
    assert sha(path)==m['sha256']
    rows=load(path)['files']
    n=sum(r['bytes'] for r in rows if not any(part in E49_EXCLUDED for part in Path(r['relative']).parts[:-1]))
    lower_bound+=n
    capacity_rows.append({'index':i,'new_source_bytes_lower_bound':n})
reserve=load(R/'admission_maven_v6.json')['minimum_free_bytes']
free=second['disk_free_bytes']
available=free-reserve
capacity={'free_bytes':free,'stop_reserve_bytes':reserve,'usable_before_guard_bytes':available,
          'pending_not_materialized':len(pending),'remaining_source_bytes_lower_bound':lower_bound,
          'minimum_headroom_after_source_only_bytes':available-lower_bound,
          'sufficient_even_for_source_only':available>=lower_bound,
          'excludes_future_build_reports_cache_and_logs':True,
          'estimate_method':'frozen manifests and exactly the E49 materialization path filter; no full job restoration'}
dump(OUT/'capacity_by_pending_class.json',capacity_rows)

# A small closed-job spot check; never hash growing archives or repeat the
# 96k-file checkpoint audit during search. This is labelled as a spot check.
spot=None
if completed:
    latest=completed[-1]['index']
    folder=R/'jobs'/f'{latest:03d}'
    entries=load(folder/'artifact_manifest.json')
    if len(entries)<=1500 and sum(r['bytes'] for r in entries)<=30_000_000:
        spot={'index':latest,'scope':'one small closed archive, not all old/live jobs','archive':verify(folder)}

started=datetime.fromisoformat(plan['started_utc'])
elapsed_total=(end-started).total_seconds()
throughput=len(completed)/(elapsed_total/3600)
advanced=(delta['runner_CPU_seconds']>0 or delta['runner_IO_read_operations']>0 or delta['runner_IO_write_operations']>0
          or delta['completed_jobs']>0 or delta['runtime_snapshot_changed']
          or any(p['name'].lower() in {'java.exe','javaw.exe'} for p in second['owned_process_tree']))
status_age=(end-datetime.fromisoformat(second['runtime_status']['updated_utc'])).total_seconds()
record={'at_utc':end.isoformat(),'assessment':'RUNNING_NO_HANG_EVIDENCE_IN_OBSERVATION' if advanced and not overdue and not overlaps else 'REVIEW_OBSERVATION_DETAILS',
        'owner_identity':identity,'samples_seconds_apart':elapsed,'observed_progress':delta,
        'owned_worker_command_overlaps':overlaps,'active_commands':active,'overdue_commands':overdue,
        'runtime_snapshot_age_seconds':status_age,'latest_job_events':last_progress[-3:],
        'v6_closed_terminal_records_seen':len(completed),'v6_closed_indices':[r['index'] for r in completed],
        'closed_job_process_build_successes':sum(r['legacy_process_build']==1 for r in completed),
        'closed_job_pipeline_failures_retained':sum(r['legacy_process_build']==0 for r in completed),
        'closed_generation_unsuccessful':sum(not r['generation_success'] for r in completed),
        'closed_complete_measurement_evidence':sum(r['strict_measurement_evidence'] for r in completed),
        'throughput_classes_per_hour_observed':throughput,'elapsed_v6_minutes':elapsed_total/60,
        'capacity':capacity,'latest_closed_archive_spot_check':spot,'read_races_omitted':read_races,
        'active_sample_index_at_observation':second['runtime_status'].get('active_sample_index'),
        'runtime_total_records_including_E49':49+second['runtime_status']['new_completed'],
        'GPT_guard_last_recorded':second['runtime_status']['GPT_guard'],
        'GPT_guard_last_checked_utc':second['runtime_status']['GPT_guard_checked_utc'],
        'new_GPT_API_calls':0,'experiment_or_process_changes':0,'config_changes':0,'paper_changes':0,
        'limitations':'Two short resource samples plus archived command history; not a guarantee of future availability, all-class audit or statistical quality assessment.'}
dump(OUT/'result.json',record)
dump(OUT/'commands_observed.json',commands)
dump(OUT/'closed_results_observed.json',completed)
local=end.astimezone(__import__('zoneinfo').ZoneInfo('Asia/Bangkok')).strftime('%d/%m/%Y %H:%M:%S')
ram=second['host_memory_available_bytes']/1e9
mem=second['owned_RSS_sum_bytes']/1e9
cap_sentence=('Dung lượng hiện có chưa đủ ngay cả cho source còn phải materialize trước khi chạm reserve.'
              if not capacity['sufficient_even_for_source_only'] else
              'Source tối thiểu hiện vẫn nằm trong khoảng dung lượng có thể dùng, nhưng build/report/cache/log mới chưa được tính; không bảo đảm đủ cho toàn bộ phần còn lại.')
text=f'''# Kiểm tra độ ổn định tiến trình B1

Thời điểm kiểm tra: **{local} (UTC+7)**. Đánh giá: **{record['assessment']}**. Không khởi động lại, dừng tiến trình, sửa config, nguồn test, metric hoặc paper trong bước chẩn đoán.

## Bằng chứng tiến trình

- Hai mẫu cách nhau{elapsed:.1f}s đều khớp owner PID/create-time/script của invocation v6. Preview được đọc từ HTTP; tuổi snapshot tại mẫu cuối:{status_age:.1f}s.
- Chênh lệch CPU runner:{delta['runner_CPU_seconds']:.3f}s; I/O read operations:{delta['runner_IO_read_operations']}; write operations:{delta['runner_IO_write_operations']}. Đây chỉ là process Python điều phối; Java con có CPU riêng, vì vậy Python CPU thấp không đồng nghĩa treo.
- Số command đang mở:{len(active)}; vượt timeout cộng30s grace:{len(overdue)}. Command history quan sát có{len(overlaps)} lần chồng lệnh của dispatcher. Nhiều JVM con trong cùng search/PIT không tự đồng nghĩa nhiều class chạy song song.
- V6 đã có{len(completed)} terminal records đóng, gồm{record['closed_job_process_build_successes']} process-build successes và{record['closed_job_pipeline_failures_retained']} pipeline failures được giữ;{record['closed_complete_measurement_evidence']} đủ measurement evidence. Failure của subject không tự là lỗi runner. Không suy mutation quality hoặc RQ từ các số vận hành này.
- Tốc độ quan sát từ đầu V6:{throughput:.1f} class/giờ trong{elapsed_total/60:.1f} phút, có tính compile/search/measurement/audit. Không phải ETA bảo đảm; độ lớn repo và failure stage có thể làm tốc độ thay đổi.
- Chỉ spot-check một closed archive nhỏ khi có thể; không audit lại toàn cohort hoặc đọc archive đang ghi. Chi tiết ở `result.json`.

## Tài nguyên và dung lượng

RAM host còn{ram:.2f}GB/{second['host_memory_total_bytes']/1e9:.2f}GB; tổng RSS cây runner/JVM quan sát khoảng{mem:.2f}GB (cộng RSS có thể đếm shared pages nhiều lần). Không có kết luận memory leak từ hai mẫu ngắn.

Đĩa còn **{free/1e9:.2f}GB**, reserve dừng **{reserve/1e9:.2f}GB**, có thể dùng trước reserve **{available/1e9:.2f}GB**. Còn{len(pending)} class chưa materialize, source tối thiểu theo snapshot/filter hiện tại là **{lower_bound/1e9:.2f}GB**; headroom sau source-only:{(available-lower_bound)/1e9:.2f}GB. {cap_sentence}

Đây là rủi ro dừng có kiểm soát ở disk guard, tách khỏi bằng chứng tiến trình hiện có/không treo. Không hạ reserve hoặc xóa bằng chứng để chạy tiếp. Nếu cần bổ sung dung lượng, phải xử lý ngoài raw evidence đã khóa và có audit riêng. Không can thiệp batch chỉ vì ước lượng này; guard hiện tại giữ nguyên.

## Giới hạn và phạm vi khoa học

Runtime đang có{record['runtime_total_records_including_E49']} kết quả gồm49 E49, active tại mẫu cuối:{record['active_sample_index_at_observation']}.12 class chưa chấm và40 Gradle chưa admit vẫn giữ nguyên; E1-full300 chưa hoàn tất. Số runtime chưa thay cho một audit cohort cuối.

GPT guard cuối được ghi `{record['GPT_guard_last_recorded']}` lúc `{record['GPT_guard_last_checked_utc']}`; không gọi đó là kiểm hash liên tục. GPT/API mới0, không repeated-run/GPT/Gradle mới trong bước kiểm. Chạy ổn định về vận hành chưa chứng minh kết quả công bằng hoàn toàn, lặp lại được giữa runs hoặc R2.1 toàn300 đã giải quyết.

Hai mẫu ngắn không chứng minh máy/ứng dụng sẽ không ngắt sau này. Nếu snapshot già, owner mất, command quá timeout hoặc có guard failure thì kiểm log/receipt trước mọi continuation; không tự restart batch.
'''
with (OUT/'REPORT.md').open('x',encoding='utf-8') as f:
    f.write(text)
dump(OUT/'manifest.json',{'files':[{'path':p.relative_to(R).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size}
                                for p in sorted(OUT.iterdir()) if p.is_file()]})
audit.log('B1_RUNTIME_STABILITY_OBSERVED_READONLY',result_sha256=sha(OUT/'result.json'),
          manifest_sha256=sha(OUT/'manifest.json'),assessment=record['assessment'],
          samples_seconds_apart=elapsed,overdue_commands=len(overdue),command_overlaps=len(overlaps),
          new_experiment_calls=0,config_changes=0)
print(json.dumps({k:record[k] for k in ['assessment','samples_seconds_apart','v6_closed_terminal_records_seen',
      'runtime_total_records_including_E49','active_sample_index_at_observation','runtime_snapshot_age_seconds',
      'throughput_classes_per_hour_observed','capacity']},indent=2))
