"""Verify first closed v6 job only; no live-job or baseline remeasurement."""
import json,sys,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
from completed_archive_guard_v3 import verify
from measurement_parser_v1 import parse
from run_maven_b1_v2 import guards

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

guards(load(R/'admission_maven_v6.json'))
folder=R/'jobs/074'
assert not (folder/'interrupted.json').exists()
job=load(folder/'job_admission.json')['job']
result=load(folder/'result.json')
assert result['terminal'] and result['sample_index_1based']==74 and result['GPT_API_calls']==0
assert result['source_guard']=='PASS' and result['production_bytecode_guard']=='PASS'
archive=verify(folder)
raw=parse(folder/'repo'/job['module'],job['focal_class'],job['package'],job['selected_test_fqcn'],result['legacy_process_build'])
assert all(result.get(k)==v for k,v in raw.items())
with urllib.request.urlopen('http://127.0.0.1:8766/status.json',timeout=5) as response:
    status=json.load(response)
assert status['new_API_calls']==0 and status['runner_invocation_version']=='v6'
at=datetime.now(timezone.utc).isoformat()
record={'status':'PASS_FIRST_CLOSED_V6_CHECKPOINT','at_utc':at,'sample_index_1based':74,
        'result_sha256':sha(folder/'result.json'),'archive_check':archive,'offline_parser':'ALL_FIELDS_IDENTICAL',
        'legacy_process_build':result['legacy_process_build'],'strict_percent':result['legacy_strict_mutation_percent'],
        'strict_measurement_evidence':result['strict_measurement_evidence'],'focal_mutants':result['focal_mutants'],
        'killed_mutants':result['killed_mutants'],'prior_verified_total':95,'verified_total':96,
        'runtime_observation':status,'new_GPT_API_calls':0,'paper_changed':False,'full300_complete':False}
dump(R/'audit/first_v6_checkpoint074_v1.json',record)
text=f'''# B1 — checkpoint hiện tại:96 class đã kiểm

Cập nhật UTC:{at}. **96/300 class có kết quả đã nghiệm thu**, gồm49 E1 tái sử dụng và47 Maven mới.074 là checkpoint mới nhất đã kiểm archive/hash/census và reparse toàn bộ trường kết quả; source/bytecode guards PASS. Không chạy lại test trong bước audit.

Invocation v6 đã mở đúng153 class Maven chưa thử có POM parse được, theo original order, worker1; đang tiếp tục sau074. Runtime quan sát: `{status['phase']}`, active `{status.get('active_sample_index')}`, liveness `{status['runner_liveness']}`. Số runtime có thể thay đổi sau snapshot; không coi class đang chạy là đã nghiệm thu.

**12 class chưa chấm** giữ trong manifest300:048/049 do JUnit3 compile scope;072/112/119/163/173/211/220/269/275/294 do POM lỗi prefix ngay trong frozen input. Không sửa POM/JUnit, không gán0, giảm denominator hoặc dùng E0 lấp E1.40 Gradle chưa admit; queue fixture sau V5 đã SKIPPED, không khởi động Gradle.

Code generation/measurement, seeds và budgets giữ nguyên. GPT/API mới0; GPT61/45/300, E0, E49,5RQ và paper15 trang không đổi. E1-full300 chưa hoàn tất; chưa đưa dữ liệu dang dở vào paper hoặc kết luận NI300. Không tự restart sau guard failure; STOP và disk reserve12GB giữ nguyên.

## Tài liệu để tiếp tục

- [Preview local](http://127.0.0.1:8766/?view=b1-v2): đọc runtime/owner; không có endpoint khởi chạy experiment.8 HTTP checks PASS; chưa kiểm browser render.
- [Phân tích đầy đủ, task, mức ảnh hưởng và ràng buộc reviewer](PROGRESS_B1_V12.md).
- [POM input review](audit/pom_input_deferrals_v2/REPORT.md): census163 POM,10 lỗi cùng signature và bằng chứng lỗi có sẵn trước generation.
- `admission_maven_v6.json`, `launch_remaining_maven153_v6.json`:153 indices và hashes; completion sẽ ở `runtime/remaining_maven153_v6_completion.json`.
- `audit/first_v6_checkpoint074_v1.json`, `audit/progress_registry_v13.json`: kiểm074 và snapshot này. Raw logs giữ riêng trong từng job/audit ledger.

Các bước tiếp theo: khép phần Maven độc lập; review compatibility của12 class chưa chấm bằng quyết định riêng; qualify Gradle provider/generation trong sandbox E sau khi Maven idle; chỉ analytic/chốt paper khi dữ liệu đủ và audit PASS. Không chạy thêm GPT/repeated subset, công khai code, bịa artifact URL, upload, đăng ký, thanh toán hoặc ký license.
'''
with (R/'PROGRESS_B1_V13.md').open('x',encoding='utf-8') as f:
    f.write(text)
paths=[Path(__file__),R/'PROGRESS_B1_V13.md',R/'PROGRESS_B1_V12.md',R/'audit/progress_registry_v12.json',
       R/'audit/first_v6_checkpoint074_v1.json',folder/'result.json',folder/'artifact_manifest.json',
       R/'admission_maven_v6.json',R/'launch_remaining_maven153_v6.json']
dump(R/'audit/progress_registry_v13.json',{'files':[{'path':p.relative_to(R).as_posix(),
     'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(set(paths))]})
audit.log('B1_FIRST_V6_CHECKPOINT074_VERIFIED',registry_sha256=sha(R/'audit/progress_registry_v13.json'),
          verified_total=96,offline_parser='ALL_FIELDS_IDENTICAL',new_GPT_API_calls=0)
print(json.dumps({k:record[k] for k in ['status','verified_total','focal_mutants','killed_mutants','new_GPT_API_calls']},indent=2))
