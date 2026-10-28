"""Record a handoff during an explicit invocation without touching live jobs.
Only immutable pre-admission archives are verified here. Live counters are a
timestamped runtime observation, not acceptance of additional experimental data.
"""
import json, sys, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone
from maven_adapter_v1 import R, sha, dump
from run_maven_b1_v2 import guards
from projection_io_v1 import publish_json

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

def load(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def main():
    lock=load(R/'admission_maven_v4.json')
    guards(lock)
    assert load(R/'validation/maven_dispatch_v4/result.json')['status']=='PASS_PURE_DISPATCH_ADMISSION_GUARDS'
    assert load(R/'runtime/non_junit4_deferrals_v1/048.json')['score'] is None
    checks=[]
    status=None
    for route, expected in [('/',200),('/status.json',200),('/manifest.json',200),
                            ('/jobs/048/native_generated.json',404),('/audit/',404)]:
        try:
            with urllib.request.urlopen('http://127.0.0.1:8766'+route,timeout=5) as response:
                code=response.status
                body=response.read()
        except urllib.error.HTTPError as ex:
            code=ex.code
            body=ex.read()
        assert code==expected
        checks.append({'route':route,'status':code})
        if route=='/status.json':
            status=json.loads(body)
        if route=='/manifest.json':
            public=json.loads(body)
            assert len(public)==300 and all(set(x)=={'sample_index_1based','class_key','repo_id','focal_class','build_tool','seed','status'} for x in public)
            assert next(x for x in public if x['sample_index_1based']==48)['status']=='INTERRUPTED_REVIEW_REQUIRED'
    assert status is not None and status['new_API_calls']==0
    at=datetime.now(timezone.utc).isoformat()
    record={'at_utc':at,'scope':'verified admission plus non-transactional live observation; no acceptance of growing job archives',
            'baseline_verified_new_results':27,'verified_reused49':49,'baseline_unscored_deferrals':[48],
            'baseline_Maven_unattempted':183,'Gradle_benchmark_unattempted':40,
            'runtime_observation':status,'http_checks':checks,'visual_QA':'not performed; browser control disabled',
            'protected585_E49_GPT_guard':'PASS','GPT_API_calls':0,'paper_modified':False,
            'full300_complete':False,'admission_sha256':sha(R/'admission_maven_v4.json')}
    dump(R/'audit/progress_v8.json',record)
    text=f'''# B1 — continuation v4 và điểm tiếp tục

Snapshot UTC: {at}. **Đã xác minh ở admission:49 E1 tái sử dụng +27 kết quả mới =76 class.** Class048 đã generation nhưng chưa measurement và chưa có điểm. Còn183 Maven chưa thử tại thời điểm mở invocation mới;40 Gradle chưa admit benchmark. E1-full300 chưa hoàn tất. Paper hiện tại không thay đổi.

## Đã xử lý

- Kiểm tra tiến trình chỉ thấy web monitor trước khi mở invocation mới; batch198 đã dừng, không còn benchmark B1 chạy ngầm ở thời điểm kiểm.
-048 dùng JUnit3.8.1 trong production compile closure và JUnit Jupiter5.6.0 ở test scope. Không nâng dependency này lên JUnit4, không đổi provider, không regenerate native suite. Archive/source/native/production bytecode và các lệnh đã kết thúc được kiểm trước khi đưa vào hàng chờ.
- Tạo dispatcher v4 riêng, kế thừa hash/admission v3. Giữ nguyên controller measurement v2, bridge v3, profile reviewer, ordered classpath/CP-file transport, tools, seeds và budgets.13 kiểm tra điều phối PASS, không chạy JVM/API trong qualification này.
- Invocation mới chỉ đi qua183 class chưa thử theo thứ tự gốc, worker1. Chỉ guard JUnit3 compile scope đã mô tả trong `NON_JUNIT4_DEFERRAL_V1.md` mới được giữ lại chưa chấm để đi tiếp class độc lập. Mọi lỗi integrity/guard khác dừng invocation; không tự restart/retry hoặc sửa dependency để ép build thành công.
- Mỗi class giữ lại có receipt riêng `score:null`; vẫn thuộc manifest300, không được gán0, không dùng E0 lấp E1 và không hạ denominator. Xử lý sau phải có quyết định riêng và dùng lại native suite đã lưu khi khả thi.

## Quan sát runtime, chưa phải nghiệm thu kết quả mới

Phase: `{status['phase']}`. Snapshot runtime UTC: `{status['updated_utc']}`. Active class: `{status.get('active_sample_index')}`. Runtime báo{status['new_completed']} kết quả mới;{status.get('maven_deferred_unscored',0)} class giữ lại chưa chấm;{status.get('maven_unattempted','?')} Maven chưa thử. Các số này có thể thay đổi sau khi ghi file này; chưa thay cho audit archive cuối invocation.

Maven chưa có kết quả trên preview bao gồm cả class chưa thử, class đang chạy và class giữ lại; chi tiết ở phần blockers/manifest. Không gọi một class chưa đo là failure0. Actual EvoSuite process starts và command plans được đếm riêng; conditional technical attempts không phải repeated-run sample độc lập.

## Gradle và phần việc tiếp theo

- Queue cũ `gradle_native_after_maven_v1` đã `SKIPPED_MAVEN_NOT_SUCCESSFULLY_COMPLETE`; không khởi động lại. Không có Gradle fixture hay benchmark mới từ queue này.
-4 launcher Gradle đã PASS version-only. Recipe mới nhất là `gradle_native_recipe_v4.py`, qua pure validation và thêm audit compile/runtime/PIT/JaCoCo JAR. `run_gradle_native_fixture_v1.py` đã chuẩn bị nhưng chưa runtime-qualified. Không chạy fixture Java đồng thời Maven benchmark.
- Audit G0 Gradle zero provenance v3 nối được cả4 trường hợp qua execution log/test/coverage/PIT.3 E0 có lỗi copy do biến `project_df_evosuite` chưa gán và1 lỗi scaffolding move trước measurement. Không sửa G0 hoặc quy chênh lệch đơn thuần cho assertions. PIT CSV không chứng minh engine version lịch sử.
- Sau invocation: audit từng terminal archive và mọi class chưa chấm, kiểm GPT/E49, rồi mới chốt xử lý môi trường chưa hỗ trợ và fixture Gradle. Giữ ngưỡng đĩa12GB; không xóa bằng chứng.
- Chỉ phân tích E1-full300 khi đủ kết quả đã nghiệm thu; E0 lịch sử300, E1 bổ sung, fixed49 và giao E1 mới tách rõ. GPT giữ nguyên61/45/300 và từng class; không thay mẫu RQ1–RQ3 bằng giao mới. Giữ5RQ. Single-run/repeated chưa hoàn chỉnh, R2.1/margin/equalized budgets/hybrid chưa được đánh fully resolved nếu thiếu bằng chứng.

## File và preview

- Admission: `admission_maven_v4.json`; launch plan: `launch_remaining_maven183_v4.json`; completion sẽ có tại `runtime/remaining_maven183_v4_completion.json` khi invocation kết thúc.
- Class048: `jobs/048/artifact_manifest.json`, `runtime/non_junit4_deferrals_v1/048.json`; policy: `NON_JUNIT4_DEFERRAL_V1.md`.
- Guard validation: `validation/maven_dispatch_v4/result.json`; snapshot/hashes: `audit/progress_v8.json`, `audit/progress_registry_v8.json`.
- Preview: http://127.0.0.1:8766/?view=b1-v2 . HTTP5 route PASS, manifest đúng300 rows/7 public fields; source và audit không được phục vụ. Chưa kiểm render qua browser vì quyền điều khiển browser bị tắt.

585 file gốc/backup, GPT và E49 guards PASS. Không có GPT/API mới; repeated subset vẫn dừng. Không công khai code hoặc artifact URL; không upload, ký license, đăng ký hay thanh toán. Bản camera-ready15 trang hiện có giữ nguyên.
'''
    with (R/'PROGRESS_B1_V8.md').open('x',encoding='utf-8') as f:
        f.write(text)
    with (R/'README_CONTINUE_V8.md').open('x',encoding='utf-8') as f:
        f.write('# Điểm tiếp tục B1 v4\n\nBáo cáo mới: [PROGRESS_B1_V8.md](PROGRESS_B1_V8.md). Preview [local](http://127.0.0.1:8766/?view=b1-v2) cập nhật trạng thái runtime. README_CURRENT.md/V7 là checkpoint cũ được giữ nguyên để audit.\n\nChỉ invocation v4 được mở trong bước này; không khởi động lại batch198, queue Gradle cũ, GPT hoặc repeated subset. Không retry048. Không sửa code đã khóa hoặc paper từ số liệu đang dở. Xem completion v4 trước khi quyết định tiếp.\n')
    paths=[R/'PROGRESS_B1_V8.md',R/'README_CONTINUE_V8.md',R/'NON_JUNIT4_DEFERRAL_V1.md',
           R/'admission_maven_v4.json',R/'launch_remaining_maven183_v4.json',
           R/'validation/maven_dispatch_v4/result.json',R/'audit/progress_v8.json',
           R/'runtime/non_junit4_deferrals_v1/048.json',R/'audit/gradle_g0_zero_provenance_v3/result.json',
           R/'audit/gradle_g0_zero_provenance_v3/REPORT.md',R/'validation/gradle_native_recipe_v4/result.json',
           R/'validation/gradle_native_fixture_preparation_v1/result.json',
           R/'validation/gradle_fixture_continuation_v1/result.json',
           R/'runtime/gradle_native_after_maven_v1/state.json']
    paths+=list((R/'src').glob('*.py'))
    dump(R/'audit/progress_registry_v8.json',{'files':[{'path':p.relative_to(R).as_posix(),
          'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(set(paths))]})
    audit.log('B1_V8_ACTIVE_HANDOFF_RECORDED',registry_sha256=sha(R/'audit/progress_registry_v8.json'),
              verified_new_at_admission=27,unscored048=True,GPT_API_calls=0,
              runtime_phase_observed=status['phase'])
    print(json.dumps({'status':'PASS_ADMISSION_GUARDS_AND_HTTP_ONLY','HTTP_routes':len(checks),
                      'runtime_phase_observed':status['phase'],'active_sample_index':status.get('active_sample_index'),
                      'verified_new_at_admission':27,'GPT_API_calls':0},indent=2))

if __name__=='__main__':
    main()
