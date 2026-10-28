"""Document historical amendments and freeze further outcome-driven adaptation.
Only new audit/working-manuscript files are created; no experiments are run.
"""
import ast,csv,json,shutil,sys
from datetime import datetime,timezone
from zoneinfo import ZoneInfo
from pathlib import Path
import psutil
from maven_adapter_v1 import R,sha,dump
from run_maven_b1_v2 import guards

B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit
OUT=R/'policy_attempt_history_v2'

def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def rel(p):return Path(p).relative_to(R.parents[1]).as_posix()
def csvrows(name):
    with (OUT/name).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

guards(load(R/'admission_maven_v6.json'))
verified=load(OUT/'verification.json')
assert verified['status']=='PASS_RECORDED_ARGV_RETRY_AND_NATIVE_SOURCE_HASH_AUDIT'
counts=verified['counts'];classes=csvrows('class_policy_history300.csv');commands=csvrows('command_history_all.csv')
assert len(classes)==300
# Check the result-selection function itself: it chooses explicit folder maps,
# never reads score data or chooses a maximum. This does not make earlier
# adoption of the maps prospective/outcome-blind.
source=R/'src/run_maven_b1_v3.py'
tree=ast.parse(source.read_text(encoding='utf-8'))
selection=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='selected_result')
selection_text=ast.unparse(selection)
assert not any(word in selection_text for word in ['mutation','score','max(','sorted('])
dump(OUT/'selection_function_check.json',{'status':'PASS_EXPLICIT_INDEX_MAPPING_NO_SCORE_READ',
     'source_path':rel(source),'source_sha256':sha(source),'function_source':selection_text,
     'limit':'Current selector is not a best-score algorithm; historical map adoption can still be post-outcome and is disclosed separately'})

timeline=[
 ('P01','E49 original generation','2026-10-23',B/'e49_driver/protocol49.json',
  'Before original fixed49 E1 outcomes; historical G0/E0 outcomes already known',
  'Assertions/MUTATION, scaffolding/runtime enabled;60s search,240s cap, original-index seeds; at most one predeclared technical CP retry',
  'Generate once under declared conditional rule; original measurement retained; later whole49 replay explicitly separate'),
 ('P02','E49 post-failure diagnostics','2026-10-23',B/'e1_compatibility_diagnostic_v1/protocol.json',
  'After original E1 failures/outcomes were inspected',
  '5 old-job cases direct test-JUnit upgrade; Surefire execution diagnosis; individual-method runtime tests for old-job48',
  'No generation; diagnostic results do not directly replace benchmark rows'),
 ('P03','Selector diagnostics old-jobs18/19','2026-10-23',B/'e1_compatibility_diagnostic_v1/selector_correction_v1/18/protocol.json',
  'After failure diagnosis, not a predeclared generation retry',
  'Exact relative regular-tests include in fresh copies; test-only execution, no PIT/new generation',
  'Excluded diagnostic; evidence informed later compatibility policy'),
 ('P04','Whole49 compatibility remeasurement','2026-10-23',B/'e49_measurement_compat_v1/protocol.json',
  'Original E1 and diagnostic outcomes already known; rule fixed before replay,18/19 measured before remaining47',
  'Conditional JUnit4 TestRule fix and exact selector; native source reused, full inherited measurement lifecycle',
  'Use complete fixed49 replay regardless of score; do not take per-class maximum; acknowledge post-hoc policy'),
 ('P05','B1 initial integration','2026-10-25',R/'admission_maven_v1.json',
  'Before the new B1 subjects; inherited E49 policy already informed by earlier outcomes',
  'Same E1 generation profile/native runtime; first003 failed measurement with missing native JUnit API',
  'Retain original003 failure and all evidence'),
 ('P06','003 diagnostics v1/v2/v3','2026-10-25',R/'measurement_result_map_v2.json',
  'After003 failed; v3 success100% on1 mutant known before map adoption',
  'v1 preflight abort;v2 dependency-only then sanity-check guard abort;v3 adds JUnit4 test dependency and measures same saved suite',
  'Mapv2 promotes v3 measurement only after outcome known. No new generation, but not a prospective/outcome-blind decision'),
 ('P07','B1 native-JUnit amendment v2','2026-10-25',R/'admission_maven_v2.json',
  'Post003 diagnosis; fixed before subsequent subject outcomes',
  'Add JUnit4.13.2:test only if absent; compile closure/existing test dependencies guarded; no JUnit3 compile upgrade',
  'Conditional support for later classes; not equal GPT treatment;003 override remains explicitly exceptional'),
 ('P08','Windows CP transport v3','2026-10-26',R/'measurement_result_map_v3.json',
  'After WinError206 but before any actual search for012/016/023',
  'Replace too-long CLI classpath transport with exact CP_file_path; source/bytecode/ordered CP/seed/options preserved',
  'Fixed recovery slots regardless of score; not repeat a search that had already run. Recovery outcomes0 retained'),
 ('P09','Native-JUnit3 deferral v4','2026-10-26',R/'admission_maven_v4.json',
  'After048 environment guard; generation done, measurement not done',
  'Unscored queue only for exact compile-scope JUnit3 guard and complete evidence; no dependency upgrade or test repair',
  'Keep fixed300 membership and saved suite; no replacement score'),
 ('P10','Saved066 reconciliation/v5','2026-10-26',R/'audit/absent_v4_runner_reconciliation_v1/result.json',
  'After runner disappeared; no exit receipt reconstructed',
  'Offline raw-log/source/bytecode verification and external archive; no generation or measurement rerun',
  'Retain existing terminal066 failure exactly, not a better diagnostic outcome'),
 ('P11','V6 fixed-input queue and execution lock','2026-10-26',R/'admission_maven_v6.json',
  'After072 preflight failure; all153 eligible inputs/rules fixed before V6 execution',
  '10 invalid frozen POMs unscored; inherited dependency/selector rules unchanged; one153-subject invocation',
  'One terminal result per class; predeclared CP retry only; no native-source repair or outcome-driven measurement replay'),
 ('P12','Synthetic qualification controls','2026-10-26',R/'validation/gradle_native_fixture_preparation_v1/result.json',
  'Component qualification only; outside focal300 cohort',
  'Maven transport controls and one Gradle2.13 saved-suite fixture; Gradle fixture failed; no Gradle corpus admission',
  'Exclude synthetic fixtures from per-class result selection and repeated-run variance claims')]
policy_rows=[]
for pid,title,date,path,timing,change,rule in timeline:
    assert path.exists()
    policy_rows.append({'policy_id':pid,'stage':title,'date_UTC':date,'timing_relative_to_outcomes':timing,
                       'change_and_scope':change,'selection_rule':rule,'evidence_path':rel(path),'evidence_sha256':sha(path)})
with (OUT/'policy_timeline.csv').open('x',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(policy_rows[0]));w.writeheader();w.writerows(policy_rows)

at=datetime.now(timezone.utc)
freeze_files={**load(R/'admission_maven_v6.json')['code_and_input_hashes'],**load(R/'admission_maven_v6.json')['tool_hashes']}
freeze={'recorded_utc':at.isoformat(),'source_of_constraint':'User explicitly requested no changes to make EvoSuite tests build; configuration locked from start to end',
        'prospective_only_not_retroactive_reclassification':True,'new_corpus_executions_authorized_by_this_audit':False,
        'outcome_driven_test_repair_allowed':False,'new_dependency_or_selector_amendments_authorized':False,
        'automatic_restart_or_retry_after_failure_authorized':False,'offline_audit_and_manuscript_editing_allowed':True,
        'historical_results_maps_and_exceptions_must_be_retained_and_disclosed':True,
        'generation_profile_locked':'E1 reviewer assertions/MUTATION60s profile; seeds original index; see protocol and actual argv',
        'effective_environment_was_identical_for_all_classes_or_all_E1_stages':False,
        'existing_V6_conditional_environment_rules_already_applied':'See per-class dependency_selector_changes.csv; do not describe these as absence of compatibility support',
        'pinned_execution_files':freeze_files,'native_hash_evidence_sha256':sha(OUT/'native_source_hash_evidence.json'),
        'selection_map_v2_sha256':sha(R/'measurement_result_map_v2.json'),'selection_map_v3_sha256':sha(R/'measurement_result_map_v3.json'),
        'further_configuration_changes':'Would be a separately labelled protocol/experiment, never silently pooled into this frozen run or justified by desired scores'}
dump(R/'EXPERIMENT_CONFIGURATION_FREEZE_20261026.json',freeze)

original=B/'final_handoff_20261025_private/manuscript'
draft=R/'manuscript_policy_audit_v1'
assert not draft.exists()
draft.mkdir()
copied=[]
for p in original.rglob('*'):
    if not p.is_file() or p.suffix.lower() not in {'.tex','.bib','.cls','.bst'}:continue
    dest=draft/p.relative_to(original);dest.parent.mkdir(parents=True,exist_ok=True)
    with p.open('rb') as f,dest.open('xb') as t:shutil.copyfileobj(f,t)
    assert sha(dest)==sha(p)
    copied.append({'original':rel(p),'original_sha256':sha(p),'copy_relative':dest.relative_to(draft).as_posix()})
method=draft/'sections/03_method.tex'
old=method.read_text(encoding='utf-8')
with (OUT/'03_method_before_policy_disclosure.tex').open('xb') as f:f.write(method.read_bytes())
start=old.index('The supplementary EvoSuite configuration (E1)')
end=old.index("\n\nAgoneTest's",start)
replacement=r'''The post-review E1 generation profile enables assertions (MUTATION), scaffolding and runtime, retaining BRANCH, a 60-second search budget, disabled test archive/separate classloader, and seed 20261023 plus the original class index. A conditional technical retry removes designated test-framework JARs only after specified initialization errors, with the same seed and profile; it is a new search attempt, not manual test repair or best-score selection. Generation and Maven measurement caps are 240 and 300 seconds.

\textbf{Environment support and amendment timing.} G0 and E0 remain archived historical treatments; neither is remeasured to mirror E1 support. After inspecting E1 failures, the fixed49 suites were remeasured under an E-only compatibility policy: upgrade a direct test-scope JUnit4 dependency only if its JAR lacks TestRule, and correct inherited Surefire2.17 leading-slash includes to the exact native test. Native Java sources were preserved; this post-hoc replay is a pipeline sensitivity, not an assertion-only effect or one unchanged end-to-end environment. A later Maven extension inherited these rules and additionally supplied missing native JUnit4 in test scope; its class003 measurement override was adopted after the diagnostic outcome was known. That extension does not replace the reported300-class baseline. The final V6 execution sealed profile, seeds, budgets and conditional integration rules before its153 subjects; recorded retries used technical markers, and final native sources matched generation-attempt archives. Stage-specific policies, suite-only diagnostics and result-selection exceptions are audited separately. No per-class maximum is selected, but post-outcome policy adoption remains a validity limitation. GPT's61/45/300 cohorts remain unchanged.'''
updated=old[:start]+replacement+old[end:]
method.write_text(updated,encoding='utf-8')
assert sha(original/'sections/03_method.tex')==next(x['original_sha256'] for x in copied if x['copy_relative']=='sections/03_method.tex')
with (draft/'README_DRAFT.md').open('x',encoding='utf-8') as f:
    f.write('# Source-only policy-disclosure draft\n\nCopied from the immutable private15-page release. Only sections/03_method.tex is changed. No PDF is supplied or claimed compiled/render-verified by this audit;15-page fit must be checked when the final result scope is settled. Existing final PDF/ZIP are unchanged.\n\nThe Methods disclosure distinguishes fixed generation options from conditional/post-hoc environment support. The historical policy/attempt ledger is in ../policy_attempt_history_v2/. No new experiments, scores, references, author metadata, artifact URL or disclosure wording have been added.\n')
dump(draft/'SOURCE_PROVENANCE.json',{'base':rel(original),'base_files':copied,'changed_file':'sections/03_method.tex',
     'before_sha256':sha(OUT/'03_method_before_policy_disclosure.tex'),'after_sha256':sha(method),
     'PDF_compiled':False,'page_limit_checked':False,'final_submission_release_changed':False})

support=r'''# Methods — mức hỗ trợ môi trường và thời điểm khóa

## Bảng để đối chiếu giữa các nhánh

|Hạng mục|GPT G0 / EvoSuite E0 lịch sử|E1 fixed49 và B1/V6|
|---|---|---|
|Dữ liệu|Giữ nguyên kết quả July300; GPT61/45/300,298 artifacts+2 no-API preprocessing rows|49 suite được tái sử dụng và phần Maven mở rộng riêng; không thay số liệu G0/E0|
|Chuẩn bị môi trường|Historical runner có sandbox, prewarming/settings và integration theo project; không được gọi là không hỗ trợ môi trường|Snapshot prepared-workspace, cache riêng, JDK8/tools.jar và E-only runtime integration; không chứng nhận pristine upstream reproduction|
|Provider/adapter|Maven common builder dùng Surefire2.22.2; EvoSuite-specific builder dùng2.17; gate BUILD SUCCESS có testFailureIgnore=true|Native ESTest/scaffolding/runtime giữ tên; thêm dependency/selector support theo stage; process gate cũ vẫn không chứng nhận assertion pass|
|Assertion/search|E0 assertions=false, scaffolding=false, no_runtime_dependency=true; không explicit seed|E1 assertions/MUTATION, scaffolding/runtime;60s, fixed original-index seeds; conditional technical CP retry|
|Sau lỗi|Không remeasure GPT/E0 để nhận E1 compatibility support|E49 JUnit/selector diagnosis rồi replay;003 missing-JUnit diagnosis/override; Windows transport recovery. Không được gộp các sự kiện này thành một policy prospective từ ban đầu|
|V6|Không chạy GPT mới|165 actual searches cho153 class,12 technical retries,125 measurement lifecycles;266 file selected native test/scaffold khớp archive;24 class có POM hỗ trợ theo rule đã khóa|
|Dependency/selector V6|Không mirror sang GPT|3 missing-JUnit additions,14 JUnit4 test-scope upgrades,7 exact selectors; rules fixed beforeV6 but effective POM differs by condition|
|Không hỗ trợ được|Historical failures giữ nguyên|10 JUnit3 compile-scope và10 frozen-POM errors chưa chấm;40 Gradle chưa benchmark; không tự sửa để đạt build|
|Compute|Một GPT API call/cap2048 tokens và60s Evo search khác loại ngân sách|Không tuyên bố equalized compute; technical attempts và measurement-only diagnostics tính riêng|

## Câu có thể xác nhận

V6 giữ đúng profile sinh, seed, timeout và rule retry đã khóa;12 retry thực tế đều có marker kỹ thuật và classpath sau retry đúng sanitizer đã định trước.266 file test/scaffold được đối chiếu với snapshot attempt sinh và bản cuối, không thấy sửa Java/assertion sau sinh. Mỗi class V6 có tối đa một lifecycle measurement; current selector chọn map theo index/path, không đọc score để lấy max.

## Câu không được xác nhận

Không thể viết “toàn bộ E1 giữ nguyên cấu hình từ đầu tới cuối”, “không có hỗ trợ để cải thiện khả năng chạy suite”, hoặc “mọi amendment đã được chốt trước khi xem outcome”. E49 dependency/selector replay và003 override là quyết định sau lỗi/outcome.003 diagnostic100% đã được biết khi mapv2 được chấp nhận; absence of a max-score algorithm không chứng minh quyết định adoption hoàn toàn độc lập outcome.

Không thể viết “không bao giờ có file test bị xóa/ghi lại”: conditional technical retry trong function đã khóa có thể bỏ file primary trước khi sinh lại; snapshot mỗi attempt vẫn giữ. Khẳng định đúng là không manual sửa nội dung Java/assertions để làm suite pass, và bytes của suite cuối khớp attempt được giữ. Khác biệt giữa stages/conditional environments vẫn phải công bố.

## Phần Methods đã tạo

Bản source riêng: `../manuscript_policy_audit_v1/sections/03_method.tex`. Chỉ thay đoạn E1/support disclosure; không sửa source/PDF/ZIP15 trang đã chốt. Đây là source draft chưa compile/render/kiểm15 trang, không phải PDF camera-ready mới. Full history không đưa vào15 trang: bảng300 class và từng command nằm trong artifact riêng tư. Wording về replication package vẫn giữ nguyên ở disclosure cũ; không tạo URL công khai.

Methods hiện mô tả các post-hoc sensitivity như giới hạn và không đưa240 terminal records hoặc các score B1 đang chờ full audit thành kết quả paper. E0 whole300, fixed49 supplement, later B1 extension và diagnostic-only executions không được nhập làm một treatment duy nhất.
'''
with (OUT/'METHODS_ENVIRONMENT_ASYMMETRY.md').open('x',encoding='utf-8') as f:f.write(support)
retry_indices=sorted({a['index'] for a in load(OUT/'V6_per_class_checks.json') if a['technical_retry']})
local=at.astimezone(ZoneInfo('Asia/Bangkok')).strftime('%d/%m/%Y %H:%M:%S')
table='\n'.join(f'|{p[0]}|{p[1]}|{p[4]}|{p[5]}|{p[6]}|' for p in timeline)
report=f'''# Audit policy và attempts — xuất lịch sử, không sửa thực nghiệm

Cập nhật **{local} (UTC+7)**. Đã xuất **300 dòng class history**, **{counts['command_or_preflight_records']} command/preflight records** và bảng thay đổi dependency/selector. Đây là lịch sử nhánh E1 đang cấp dữ liệu cho B1 và các diagnostics liên kết; G0/E0 giữ như historical references. Không suy đoán attempt thiếu log của mọi bản nháp bỏ dở hoặc biến synthetic/repeated-subset trials thành benchmark evidence.

## Kết luận chính

**V6 generation/profile và recorded retries PASS kiểm tra**, nhưng **không thể xác nhận toàn bộ E1 có một effective configuration bất biến từ lần đầu đến cuối**. Đã có post-failure dependency/selector amendments và suite-only remeasurements trước V6. Các ngoại lệ này phải được nêu trong Methods và result provenance, không xóa dấu vết hoặc đổi tên thành predeclared retry.

- V6 có{counts['V6_generation_processes']} actual generation processes cho153 class;{counts['V6_subjects_with_technical_retry']} class có technical retry. Seed, profile,240s cap và exact sanitized CP đều khớp rule đã khóa. Indices retry:`{retry_indices}`.
- V6 có{counts['V6_measurement_lifecycles']} measurement lifecycles; tối đa một/class, các class generation fail/guard stop không có measurement. Không có chu kỳ đo lại theo score trong V6.
- **{counts['V6_native_source_files_checked']} file native test/scaffold V6** khớp hash snapshot của attempt sinh và bản cuối. Không thấy manual sửa assertion/Java source trong bằng chứng đã ghi. Đây là kiểm saved artifacts/endpoints, không phải bảo đảm tuyệt đối chống mọi thao tác không ghi log giữa các checkpoint.
- V6 POM cuối khớp policy record và classpath delta guards. Điều này là **thực hiện đúng conditional rules**, không phải POM không hề đổi.3 class missing-JUnit additions:`{counts['V6_missing_JUnit_addition_indices']}`;14 JUnit4 upgrades:`{counts['V6_JUnit4_upgrade_indices']}`;7 selectors:`{counts['V6_selector_change_indices']}`.
- Current result selector chỉ dùng index/path mapping, không đọc score/max. Tuy nhiên class003 diagnostic override được adopt sau khi biết success100%/1mutant; không thể chứng nhận quyết định adoption đó là prospective hoặc outcome-blind.

## Phân biệt các loại attempt

|Loại|Có sinh suite mới?|Dùng để chọn kết quả?|Cách báo|
|---|---|---|---|
|Primary E1 search|Có|Một result theo policy đã khai báo|Không gọi là repeated variance evaluation|
|Predeclared technical sanitized retry|Có, cùng seed/profile; CP lọc đúng danh sách|Giữ output sau technical policy, không best-of-score|Đếm actual search riêng; marker/argv/hash nằm trong attempts CSV|
|E49 diagnostic JUnit/selector/method tests|Không|Không trực tiếp thay row benchmark|Post-failure diagnostic; single-method success không thành suite pass|
|Whole49 compatibility replay|Không, dùng native suite đã khóa|Chọn toàn49 replay; không lấy max từng class|Post-hoc pipeline sensitivity; cả failures và byte/provenance guards giữ|
|003 diagnosticsv1/v2/v3|Không|Chỉ v3 được mapv2 promote sau khi biết outcome|v1 preflight abort;v2 sanity-check guard abort trước measurement;v3 measurement-only. Đây là ngoại lệ hậu nghiệm|
|012/016/023 transport recovery|Có, nhưng initial launch chưa spawn nên là lần search thực đầu|Mapv3 chốt trước actual search, giữ outcome kể cả0|Sửa transport sau WinError206; không gọi là predeclared ngay từ đầu toànE1|
|066 offline recovery|Không|Giữ result cũ nguyên byte|Không có search/measurement retry; archive thiếu được đối chiếu riêng|
|JUnit3/POM deferrals|Không có measurement mới|Không score hoặc zero-fill|Giữ đủ mẫu300; không nâng compile dependency/sửa POM để làm pass|
|Synthetic Gradle/Maven fixtures|Tổng hợp; không focal300|Không được đưa vào benchmark|Qualification, không repeated subset hoặc class result|

## Timeline policy

|ID|Stage|Thời điểm so với outcomes|Thay đổi|Quy tắc chọn|
|---|---|---|---|---|
{table}

Ngày/hash/đường dẫn bằng chứng ở `policy_timeline.csv`. UTC trong ledger; nếu record cũ không có timestamp và không khớp ledger thì ghi unavailable, không dùng mtime giả làm thời gian thực thi. Attempt ID là ID xuất bảng, không hứa là một global chronological sort; phase/command ordinal và event_time giữ thứ tự có bằng chứng.

## Các ngoại lệ không được giấu

**003:** initial missing-JUnit failure và mọi diagnostic còn nguyên. Diagv1 không chạy lệnh;v2 chỉ audit dependency/POM rồi guard chặn java-version trước measurement;v3 đo lại suite với test-JUnit addition. Mapv2 được ghi khi đã biết cả initial0 và diagnostic100. Có rule áp dụng cho các class tiếp theo, nhưng không biến003 thành một treatment nguyên thủy không sửa sau outcome.

**E49:**5 test-JUnit và2 selector cases được chẩn đoán rồi đo lại toàn49. Recorded process gate không đổi ở49 cases (legacy gate có testFailureIgnore); saved strict scores đổi ở original sampling indices `{counts['E49_saved_score_changed_after_replay_indices']}`. Vì vậy gate không đổi không chứng minh environment/quality outcome không bị tác động.

**Windows:**012/016/023 có original launch plans nhưng0 actual search starts trước recovery. Rule chọn recovery bất kể score được chốt trước actual searches;012/023 license failures và016 timeout vẫn giữ0. Không tăng budget hoặc sửa test để tìm pass.

**V6:** fixed rules có thể giúp native suites chạy được bằng dependency/selector support. Không thể thay điều này bằng câu “không sửa gì để build được”. Phát biểu được kiểm chứng là không sửa nội dung test thủ công, không thêm per-class adaptation theo score, và rule/environment khác nhau đã khai báo. Retry kỹ thuật có thể xóa file primary trước khi generator ghi suite mới theo code đã khóa; cả attempt snapshots được giữ.

## Methods và khóa hiện tại

- [Mức hỗ trợ môi trường GPT/E0/E1 và đoạn Methods](METHODS_ENVIRONMENT_ASYMMETRY.md).
- Source draft riêng:`../manuscript_policy_audit_v1/sections/03_method.tex`; source/PDF/ZIP release cũ nguyên vẹn. Draft chưa compile/render/kiểm15 trang; không giao nó như PDF camera-ready cuối.
- `../EXPERIMENT_CONFIGURATION_FREEZE_20261026.json` ghi ràng buộc hiện tại và hashes execution files/tool/native evidence/maps. Không mở thêm test repair, dependency/selector amendment, adaptive retry hoặc corpus execution trong audit này. Khóa hiện tại không hồi tố các policy đã thay đổi.
- Giữ nghiên cứu5RQ/G0/E0/fixed49 và score definition; không tính metric mới hoặc chọn hàng theo hướng giữ kết luận. Full300 E1 vẫn chưa có kết quả đủ vì20 chưa chấm+40 Gradle chưa benchmark. Không đánh R2.1/equal budgets/margin/hybrid/repeated evaluation fully resolved.

## Files chính

1. `CLASS_HISTORY300.md` và `class_policy_history300.csv`: từng class, số searches/replays/diagnostics, dependency/selector changes, initial/selected result, chọn theo rule nào và post-hoc flag.
2. `generation_measurement_diagnostic_attempts.csv`: từng generation/test/measurement/preflight có process_started, seed/timeout/marker, selector, path/hash/log và selection role.
3. `command_history_all.csv`: cả compile/dependency/effective-POM/version audits; không cộng mọi command thành một generation attempt.
4. `dependency_selector_changes.csv`, `policy_timeline.csv`: thay gì, khi nào so với outcome, vì sao và hash bằng chứng.
5. `verification.json`, `V6_per_class_checks.json`, `native_source_hash_evidence.json`, `selection_function_check.json`: kiểm V6 và giới hạn của xác nhận.
6. `selection_current.json`: full current map. Không tự đổi selected result/score trong bước này.

Artifacts ở workspace riêng tư, không public code/URL. Không API, không Java/Gradle/EvoSuite mới, không đổi raw evidence, author metadata hoặc disclosure wording.585 original/backup và GPT/E49 guards PASS; không upload, thanh toán, đăng ký hoặc ký license.
'''
with (OUT/'REPORT.md').open('x',encoding='utf-8') as f:f.write(report)
manifest_paths=list(OUT.iterdir())
manifest_paths=[p for p in manifest_paths if p.is_file()]
manifest_paths += [R/'EXPERIMENT_CONFIGURATION_FREEZE_20261026.json']+list(p for p in draft.rglob('*') if p.is_file())
dump(OUT/'PACKAGE_MANIFEST.json',{'recorded_utc':at.isoformat(),'files':[{'path':rel(p),'sha256':sha(p),'bytes':p.stat().st_size}
    for p in sorted(set(manifest_paths))]})
audit.log('B1_POLICY_HISTORY_METHODS_AND_CURRENT_FREEZE_WRITTEN',manifest_sha256=sha(OUT/'PACKAGE_MANIFEST.json'),
          execution_freeze_sha256=sha(R/'EXPERIMENT_CONFIGURATION_FREEZE_20261026.json'),
          new_method_source_sha256=sha(method),old_manuscript_unchanged=True,new_experiment_calls=0,GPT_API_calls=0)
print(json.dumps({'history_report':str(OUT/'REPORT.md'),'classes':300,'V6_actual_generations':counts['V6_generation_processes'],
                  'V6_technical_retry_classes':counts['V6_subjects_with_technical_retry'],'V6_native_files_checked':counts['V6_native_source_files_checked'],
                  'Methods_draft':str(method),'PDF_compiled':False,'original_release_changed':False,
                  'new_experiment_calls':0},indent=2))
