"""Create human-readable audit derivatives only; no experiment execution."""
import csv,json,hashlib,sys
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone,timedelta
R=Path(__file__).resolve().parents[1];O=R/'audit_e1_execution_20261028_v2';F=R/'completion_amendment_v1/final300_offline_v1';H=R/'policy_attempt_history_v2';B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B));import audit
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(name,s):
 with (O/name).open('x',encoding='utf-8') as f:f.write(s)
def export(name,rows):
 with (O/name).open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader()
  for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in r.items()})
def link(p,label=None):return '['+(label or Path(p).name)+'](<'+str(Path(p).resolve()).replace('\\','/')+'>)'
def esc(v):return str(v).replace('|','\\|').replace('\n',' ')
def table(head,rows):return '\n|'+'|'.join(head)+'|\n|'+'|'.join(['---']*len(head))+'|\n'+''.join('|'+'|'.join(esc(v) for v in row)+'|\n' for row in rows)+'\n'
def local(t):return datetime.fromisoformat(t).astimezone(timezone(timedelta(hours=7))).strftime('%d/%m %H:%M:%S') if t else 'Không chạy'
rows=load(O/'classes300.json');s=load(O/'summary.json');stats=load(F/'statistics.json');raw=load(O/'RAW_PIT_RECHECK.json');cmds=load(O/'command_attempts.json');manifest=load(R/'manifest300.json');frozen=load(F/'class_results300.json')
with (H/'class_policy_history300.csv').open(encoding='utf-8-sig',newline='') as f:old={int(x['index']):x for x in csv.DictReader(f)}
assert len(rows)==len({r['class_key'] for r in rows})==300
assert s['input_hash_issues']==[] and raw['summary']['verified_selected_raw_PIT_reports']==221
bycmd=defaultdict(list)
for c in cmds:bycmd[c['index']].append(c)
labels={
'VALID_OBSERVED_PIT':'Có PIT quan sát hợp lệ',
'NO_FOCAL_MUTANTS':'Không có focal mutant; tỷ lệ không xác định',
'LICENSE_CHECK_FAILURE':'Lifecycle bị license-header check chặn',
'GENERATION_PROCESS_TIMEOUT':'Timeout tiến trình sinh',
'GENERATOR_INTERNAL_COMPILE_PROVIDER_FAILURE':'Lỗi compiler/provider nội bộ EvoSuite',
'GENERATION_CLASS_LOADING_OR_INIT':'Lỗi nạp/khởi tạo class',
'GENERATION_UNSUPPORTED_BYTECODE':'Bytecode không được công cụ hỗ trợ',
'JUNIT3_TEST_ONLY_PIT_UNQUALIFIED':'JUnit3: chỉ được qualify test, chưa qualify PIT',
'PIT_MINION_FAILURE':'PIT coverage minion kết thúc bất thường',
'ADAPTER_TASK_BEFORE_GENERATION':'Thiếu task adapter trước generation',
'WHOLE_MEASUREMENT_TIMEOUT':'Timeout toàn lifecycle đo; report chưa hoàn chỉnh',
'NATIVE_TEST_EXECUTION_FAILURE':'Native test thất bại, chưa tới PIT',
'GENERATION_INSTRUMENTATION':'Lỗi instrumentation trong generation'}
history=[]
for r,m,f in zip(rows,manifest,frozen):
 assert r['class_key']==m['class_key']==f['class_key']
 x={k:v for k,v in r.items() if k!='evidence'}
 x['source_commit']=m['commit_sha'];x['source_path_case_preserved']=m['focal_path'];x['focal_source_sha256']=m['source_candidate']['focal_sha256']
 x['historical_dependency_selector_changes']=json.loads(old[r['index']]['dependency_selector_changes_json'])
 x['historical_selection_rule']=old[r['index']]['selection_rule']
 x['final_selection_note']='Selected checkpoint result; do not infer original policy was prospective'
 x['raw_reports']=f['raw_reports'];x['G0_build']=f['G0_build'];x['G0_strict']=f['G0_strict'];x['E0_build']=f['E0_build'];x['E0_strict']=f['E0_strict']
 x['command_record_paths']=[c['record_path'] for c in bycmd[r['index']]]
 history.append(x)
export('class_history300.csv',history)
write('class_history300.json',json.dumps(history,ensure_ascii=False,indent=2)+'\n')
repos=[]
for rid in sorted({r['repo_id'] for r in rows}):
 rr=[r for r in rows if r['repo_id']==rid]
 repos.append({'repo_id':rid,'classes':len(rr),'generation_started':sum(r['any_generation_started'] for r in rr),'complete_suites':sum(r['has_complete_suite'] for r in rr),'observed_PIT':sum(r['has_observed_PIT'] for r in rr),'policy_zero':sum(r['score_basis']=='CONVENTIONAL_PIPELINE_FAILURE_ZERO_NOT_OBSERVED' for r in rr),'end_to_end_unknown':sum(r['end_to_end_score_percent'] is None for r in rr),'gate_pass':sum(r['process_gate']==1 for r in rr),'gate_fail':sum(r['process_gate']==0 for r in rr),'gate_unknown':sum(r['process_gate'] is None for r in rr),'categories':dict(Counter(r['category'] for r in rr))})
export('repository_summary30.csv',repos)
overview='# Bảng trạng thái và lịch sử 300 class E1\n\nChỉ số là sampling index gốc 1–300; không phải số job cũ của E49. `class_key` dùng để ghép. Dấu — là chưa có giá trị, không phải 0. G = số tiến trình generation thực sự khởi chạy; M = số lifecycle đo PIT được nhận diện; không cộng lệnh compile/dependency/test-only vào M.\n'
overview+=table(['ID','Class','G/M','Generation','Test','PIT / lý do','Gate','PIT %','E2E %'],[[r['index'],r['focal_class_name'],f"{r['actual_generation_processes']}/{r['measurement_processes']}",r['generation'],r['test_execution'],labels[r['category']],r['process_gate'] if r['process_gate'] is not None else '—',r['observed_mutation_percent'] if r['observed_mutation_percent'] is not None else '—',r['end_to_end_score_percent'] if r['end_to_end_score_percent'] is not None else '—'] for r in rows])
overview+='\n## Chi tiết từng class và đường dẫn audit\n'
for r in history:
 overview+=f"\n### {r['index']:03d} — {r['focal_class_name']}\n\n- Key: `{r['class_key']}`; commit `{r['source_commit']}`; seed `{r['seed']}`.\n- Source: `{r['source_path_case_preserved']}`; SHA256 `{r['focal_source_sha256']}`.\n- Kết quả được chọn: {link(r['selected_result']['path'])}; SHA256 `{r['selected_result']['sha256']}`.\n- Các phase: {', '.join(r['phases'])}.\n- Dependency/selector lịch sử: `{json.dumps(r['historical_dependency_selector_changes'],ensure_ascii=False)}`.\n- Quy tắc lịch sử: {r['historical_selection_rule']}. Quy tắc completion sau đó xem báo cáo chính; selected_result ở trên là checkpoint cuối.\n"
 overview+=table(['Phase','Bước','Đã start','Kết thúc / rc','Plan/receipt'],[[c['phase'],c['stage'],c['started'],c['termination_reason'] or c['returncode'],link(c['record_path'])] for c in bycmd[r['index']]])
write('CLASS_HISTORY300.md',overview)
md='''# Audit toàn bộ tiến trình E1 — checkpoint hiện tại

Ngày kiểm tra: 28/10/2026. Phạm vi là toàn bộ 300 class và lineage thực nghiệm được chọn: E49, B1 Maven V1–V6, Gradle và completion amendment. Bao gồm diagnostics có liên kết; không gộp synthetic fixtures, repeated subset hoặc các nhánh nháp không được chọn vào benchmark. Đây là audit đọc dữ liệu, không chạy thêm GPT/API, EvoSuite, Maven hay Gradle; không đổi dữ liệu gốc hoặc manuscript.

## 1. Kết luận và cách đếm

**300 class đã được đối chiếu, nhưng E1 chưa phải bộ 300 điểm mutation đo đầy đủ.** 290 class đã thực sự khởi chạy generation; 253 có suite native xuất đầy đủ. Trong 253 class này, 221 có PIT quan sát hợp lệ và 32 chưa có điểm PIT quan sát. 37 class còn lại đã chạy generation nhưng không có suite hoàn chỉnh; 10 class bị adapter chặn trước generation.

'''
md+=table(['Trạng thái','Số class','Mẫu số / diễn giải'],[
['Cohort cố định',300,'30 repositories; 260 Maven + 40 Gradle'],['Generation đã khởi chạy',290,'96,67% toàn mẫu; không có nghĩa generation thành công'],['Suite xuất hoàn chỉnh',253,'84,33% toàn mẫu; không đồng nghĩa suite pass'],['PIT quan sát hợp lệ',221,'73,67% toàn mẫu; trong đó 41 điểm 0% quan sát'],['Có suite nhưng chưa có PIT quan sát',32,'10,67% toàn mẫu; 12,65% trong 253 suite'],['Generation không xuất được suite hoàn chỉnh',37,'Không đồng nghĩa 37 compile fail của project'],['Adapter chặn trước generation',10,'Không được gọi là test build fail'],['Điểm E2E quy ước 0, không phải PIT quan sát',58,'37 generation + 8 license + 10 minion + 1 test fail + 2 timeout đo'],['E2E chưa xác định',21,'10 JUnit3 + 10 thiếu task + class6 không có mutant']])
md+='''Phân hoạch không trùng: **300 = 221 PIT quan sát + 58 zero theo policy + 21 unknown**; đồng thời **300 = 253 suite hoàn chỉnh + 37 generation không thành công + 10 chưa generation**. “12 unresolved” chỉ là nhóm chưa đo đủ trong completion30 (10 JUnit3 và 112/269), không phải số unknown của toàn300. 112/269 có PIT unresolved nhưng E2E theo policy là 0; class6 có gate pass nhưng mutation undefined.

'''
md+=table(['Build tool','N','Suite đầy đủ','PIT hợp lệ','Suite thiếu PIT','Gen không thành công','Chưa gen'],[[b,v['classes'],v['complete_suites'],v['observed_PIT'],v['complete_suite_without_observed_PIT'],v['gen_unsuccessful'],v['not_started']] for b,v in s['build_tool_counts'].items()])
md+='''## 2. Class nào có suite nhưng chưa đo được?

Các nhóm dưới đây không trùng nhau. “License check” là lỗi lifecycle, không phải lỗi cấp phép sử dụng EvoSuite. “Minion failure” xác nhận lỗi subprocess đo coverage của PIT; không tự suy nguyên nhân sâu hơn từ UNKNOWN_ERROR.

'''
md+=table(['Nhóm','N','Sampling indices'],[[labels[k],len(rr),', '.join(str(r['index']) for r in rr)] for k in dict.fromkeys(r['category'] for r in rows if r['complete_suite_without_observed_PIT']) for rr in [[r for r in rows if r['complete_suite_without_observed_PIT'] and r['category']==k]]])
md+=table(['ID','Class','Test execution','Nguyên nhân / giới hạn','E2E'],[[r['index'],r['focal_class_name'],r['test_execution'],labels[r['category']],r['end_to_end_score_percent'] if r['end_to_end_score_percent'] is not None else 'unknown'] for r in rows if r['complete_suite_without_observed_PIT']])
md+='''- **10 PIT minion:** test execution có bằng chứng PASS; lỗi nằm ở measurement. Không gọi là suite compile fail.
- **10 JUnit3:** giữ nguyên suite, chạy phần test đã qualify; PIT không được admit vì qualification provider/minion thất bại. Không có 10 lần PIT benchmark mới trong completion này. Test-only BUILD SUCCESS không bằng verify+PIT gate.
- **112/269:** native test PASS, lifecycle đo hết cap 300s. Raw partial report được giữ nhưng không được dùng để tính mutation quan sát. Không kéo dài timeout hoặc đo lại để lấy điểm.
- **175:** native tests FAIL; lifecycle dừng trước PIT. Đây là lỗi thực thi test, không phải bằng chứng compile fail.
- **6:** test PASS, process gate pass nhưng không có focal mutant; phép chia không xác định, không gọi 0%.

## 3. Class đã chạy generation nhưng không xuất suite hoàn chỉnh

'''
md+=table(['Lỗi terminal ở generation','N','Indices'],[[labels[k],len(rr),', '.join(str(r['index']) for r in rr)] for k in dict.fromkeys(r['category'] for r in rows if r['generation']=='UNSUCCESSFUL') for rr in [[r for r in rows if r['generation']=='UNSUCCESSFUL' and r['category']==k]]])
md+='''4 class **19, 33, 76, 182** có lỗi compiler/provider bên trong EvoSuite (`JUnitAnalyzer.compileTests`, `ServiceConfigurationError`, Trimou provider “not a subtype”, qua annotation processor). Log từng class báo đã tạo test ứng viên, nhưng không có cặp test/scaffold hoàn chỉnh được xuất. Một số tiến trình vẫn trả rc=0; do đó rc=0 không đủ để chứng nhận generation thành công.

Ngoài 4 class trên, 5 class timeout **29,146,165,214,287** cũng có thông báo test ứng viên trước khi thất bại. Tổng cộng **9 class generation không thành công có thông báo Generated ... tests**; không cộng 9 này vào 253 suite hoàn chỉnh. Thông báo mutation/coverage nội bộ của EvoSuite không phải report PIT của nghiên cứu. Nếu hiểu “đã sinh” là từng có test ứng viên, cần nói rõ thêm 9 ca này; nếu hiểu là suite đã lưu đầy đủ, con số thiếu PIT là 32.

Bytecode không hỗ trợ có thể thuộc dependency trong phân tích của EvoSuite/ASM; không suy toàn bộ business source dùng sai JDK chỉ từ thông báo major version. Class246 có lỗi instrumentation `IllegalArgumentException: Size mismatched`; giữ là lỗi generation, không tự gán cho chất lượng assertions.

## 4. Class chưa thực sự generation

'''
md+=table(['ID','Class','Lý do'],[[r['index'],r['focal_class_name'],labels[r['category']]] for r in rows if r['generation']=='NOT_STARTED_ADAPTER_BLOCK'])
md+='''10 class này không có task adapter cần thiết được resolve/register. Raw legacy failure được giữ để tái lập, nhưng bảng evidence-aware giữ gate/score unknown. 10 POM lỗi chuẩn bị ban đầu là nhóm khác và đã được bổ sung execution sau khi truy nguồn/restore đúng input.

## 5. Lịch chạy và lịch thay đổi policy

Thời gian dưới đây là UTC+7, từ timestamp trong command/receipt; cột cuối là lần **khởi chạy lệnh cuối**, không phải thời điểm hoàn tất phase. Không dùng mtime hoặc created_utc của admission kế thừa làm thời điểm thực nghiệm. Các phase có thể chồng lấn class; không cộng số class theo phase để suy cohort.

'''
md+=table(['Phase','Class liên quan','Gen processes','Lifecycle PIT','Start đầu','Start lệnh cuối'],[[p['phase'],p['class_count'],p['generation'],p['measurement'],local(p['first_utc']),local(p['last_command_start_utc'])] for p in sorted(s['phase_counts'],key=lambda x:x['first_utc'] or '')])
md+='''- **E49:** sinh49 suite, đo lần đầu, chẩn đoán JUnit/selector, rồi replay phép đo toàn49 trên suite nguyên byte. Không sinh lại49. Saved score đổi tại131,230,233,237,281; gate49 không đổi không có nghĩa môi trường không ảnh hưởng kết quả.
- **Class3:** dùng lại suite cũ, thêm test-JUnit và đo lại; diagnostic100% trên1mutant đã được biết khi adopt mapping. Đây là ngoại lệ hậu nghiệm; không chứng nhận outcome-blind. Bảng sensitivity giữ initial0.
- **12/16/23:** ban đầu WinError206 khiến launcher chưa spawn generation; CP_file transport recovery là lần search thực đầu, không phải repeat một search đã chạy. Không che các outcome thất bại sau recovery.
- **V6:**153 class,165 generation processes,12 retry kỹ thuật;125 lifecycle đo, tối đa một/class. Rules khóa trước V6 nhưng hình thành sau các lỗi ở phase trước.
- **Gradle40:**30 class tới generation,10 chưa có task;20 suite hoàn chỉnh. 10 suite nhóm Spikes được đo PIT bổ sung sau sửa resolve adapter, không regenerate.
- **Completion30:**10 Gradle PIT giữ suite;10 JUnit3 giữ suite và chỉ test đã qualify;10 POM restore input có provenance rồi generation khi chưa có suite. Kết thúc18 PIT hợp lệ và12 chưa có phép đo hoàn chỉnh.
- **Class72:** đã sinh suite rồi source guard dừng tại `.flattened-pom.xml` do plugin có sẵn tạo lại. Annex cho phép đúng derived file này, không bỏ guard source tổng quát; continuation chỉ đo suite cũ. Đây là readmission sau lỗi, không phải predeclared generation retry.
- **Class112:** report bị cắt khi timeout; parser amendment từ chối partial report áp dụng toàn300. Không sửa công thức điểm và không retry112. Class269 về sau cùng cách xử lý.
- **Pause/resume:** checkpoint sau173 có25 class được chấp nhận trong completion30 (bao gồm class đang chạy khi yêu cầu dừng), còn211,220,269,275,294. Resume xử lý211/220/269; worker biến mất trước generation275, nguyên nhân chưa xác định. Log đã đính chính nhầm đơn vị dung lượng:12GB decimal khác12GiB; không được khẳng định disk-full gây dừng. Resume cuối chạy275/294, hoàn tất checkpoint27/10 khoảng14:56 UTC+7. Không chạy lại các class đã nghiệm thu.

Policy completion là **bổ sung sau khi đã quan sát lỗi**, không prespecified từ đầu nghiên cứu. POM restore đối chiếu đúng commit, giữ business source/dependency production; JUnit3 giữ production JUnit3, bổ sung hỗ trợ ở test tooling; Gradle PIT bổ sung resolve công cụ offline, giữ engine/mutators/target đã khóa. Xem các annex được link cuối báo cáo để có giới hạn chính xác.

## 6. Attempts, cấu hình và tính công bằng

'''
md+=f"Có **{s['counts']['actual_generation_processes']} generation processes cho290 class**:15 retry kỹ thuật tại {', '.join(map(str,s['counts']['technical_retry_classes']))}. Riêng V6 là12 retry;3 trước V6 là19,29,33. Có292 lifecycle đo PIT trên242 class; số này bao gồm replay/continuation, không phải292 kết quả đo hợp lệ hoặc292 class độc lập. Có2195 command-plan records,2190 actual command starts,5 plan chưa start;40 trạng thái historical NOT_ATTEMPTED được giữ riêng.\n\n"
md+='''Đã kiểm lại305 lệnh generation: options/seed/cap khớp profile khóa. Seed=20261023+sampling index gốc; search60s; cap process240s; assertions=true, assertion_strategy=MUTATION, scaffolding=true, runtime dependency được giữ, criterion=BRANCH, test_archive=false, separate_classloader=false. Maven measurement cap300s; Gradle stage cap900s. Retry kỹ thuật tối đa một theo marker/sanitized classpath, cùng seed/profile; không best-of-score. Đây không phải repeated-run evaluation để định lượng variance.

Historical V6 audit còn đối chiếu exact sanitized classpath cho12 retry và266 file native test/scaffold. Không thấy manual sửa Java/assertions giữa các snapshot được lưu. Kiểm hash các endpoint không chứng minh tuyệt đối không có thao tác không ghi log ở giữa.

**Không thể xác nhận “toàn E1 giữ nguyên effective configuration từ đầu tới cuối”.** Có post-failure JUnit/selector/adapter amendments và measurement-only replay. V6 tự nó thực hiện conditional rules đã khóa:3 missing-JUnit additions(183,187,278),14 test-JUnit upgrades(107,186,193,209,217,234,238,253,256,258,270,291,296,297),7 selectors(77,99,157,226,232,259,289). Không chỉnh nội dung test khác với không hỗ trợ môi trường để test chạy được.

GPT/G0 và E0 giữ dữ liệu lịch sử. E1 nhận native runtime/scaffolding, JDK/tool preparation, JUnit/selector support và adapter amendments sau review mà GPT không nhận qua một lần chạy đối xứng. Vì vậy không quy toàn bộ chênh lệch cho assertions, không khẳng định equalized compute hoặc môi trường công bằng chỉ vì GPT được giữ nguyên. Tập giao mới60 class chỉ là chẩn đoán riêng; không thay mẫu GPT gốc của RQ1–RQ3 hoặc fixed49.

## 7. Build, test và measurement phải tách riêng

'''
md+=table(['Evidence stage','Kết quả'],[[k,json.dumps(v,ensure_ascii=False)] for k,v in stats['stage_counts'].items()])
md+='''Process gate evidence-aware: **222 pass /58 fail /20 unknown**. Tỷ lệ trên280 gate đã biết=79,29%, CI repository95%[65,36;91,79]; bounds trên300=[74,00;80,67]%, không phải CI. Không gọi tỷ lệ này là test-suite pass rate.

Native execution:240 PASS,4 FAIL(74,108,175,247),4 SKIPPED_OR_INCOMPLETE(10,58,239,289),52 NOT_EVIDENCED. Các ca74/108/247 vẫn có valid PIT do lịch sử lifecycle cho phép tiếp tục sau test failure;175 dừng trước PIT. 6 ca có valid PIT nhưng native suite không hoàn toàn pass là10,58,74,108,247,289. Không giấu chúng dưới nhãn BUILD SUCCESS.

16 gate-pass flags đã được rà:9 thiếu dòng JaCoCo focal(17,52,60,132,137,150,160,250,261) vẫn có valid PIT;6 suite không hoàn toàn pass nêu trên vẫn có valid PIT;class6 có0 focal mutants. Thiếu JaCoCo không tự làm PIT report vô hiệu. NOT_EVIDENCED là thiếu bằng chứng bước tương ứng, không được tự đổi thành compile failure.

## 8. Công thức điểm và thống kê từ checkpoint

Đã đọc lại221 raw PIT CSV, kiểm hash/focal source/package và số mutants: khớp toàn bộ score đã chọn. Công thức `round(100*KILLED/all focal mutants,2)`; gồm nested classes theo quy tắc focal SourceFile+package. TIMED_OUT nằm trong mẫu số, không cộng vào KILLED. Report không hoàn chỉnh hoặc lifecycle đo thất bại không cung cấp observed score.

**294 ServerRpcHandler:**44 mutants =38 NO_COVERAGE+6 TIMED_OUT;KILLED=0;observed0%,8 native tests pass. Đây là report hoàn chỉnh có mutant timeout, khác112/269 bị timeout toàn phép đo. 41 class có0% PIT thực sự phải tách khỏi58 conventional pipeline zeros. E0 raw provenance riêng chưa đủ để chứng nhận từng report E0; không suy độ đầy đủ đó từ việc chung công thức implementation.

'''
cohorts=stats['cohorts'];md+=table(['So sánh / estimand','N','G0 mean','Đối chứng mean','G0−đối chứng (pp)','95% CI delta theo repo'],[[name,v['n'],f"{v['left']['mean']:.2f}",f"{v['right']['mean']:.2f}",f"{v['left_minus_right']['mean']:.2f}",'; '.join(f'{z:.2f}' for z in v['left_minus_right']['CI95_repository_percentile'])] for name,v in cohorts.items() if 'left' in v])
obs=cohorts['E1_observed_PIT_only'];md+=f"E1 observed-only221: mean {obs['mean']:.2f}%, CI95% [{obs['CI95_repository_percentile'][0]:.2f};{obs['CI95_repository_percentile'][1]:.2f}],24 repositories. Đây là tập có report, không là full300 mean.\n\n"
md+='''279 available E2E gồm221 observed+58 policy-zero, không phải279 điểm PIT quan sát. Whole-repository bootstrap20.000 draws, seed20261023, giữ cặp, class-weighted mean; CI có điều kiện trên tập phân tích, không giải quyết thiên lệch do missing/support asymmetry.

Full300 có21 E2E unknown: mean E1 bounds[31,8842;38,8842]%;G0−E1 bounds[−27,0274;−20,0274]pp. Đây là bounds tất định, không CI. Zero-fill chỉ sensitivity; không điền0 vào21 unknown trong bảng chính. Sensitivity giữ112/269 unknown thay vì policy-zero làm23 unknown; bỏ/giữ unknown6 nonpassing suite được báo riêng trong statistics.json. Không dùng các kết quả này để gọi E1-full300 hoàn chỉnh hay chứng minh NI toàn300.

## 9. Kiểm chứng, giới hạn và bàn giao

Audit đã kiểm11.912 file nguồn bằng chứng duy nhất;1.018 lượt đối chiếu native source hash (có thể trùng file giữa snapshots), không có mismatch trong phạm vi đó. Hash kiểm toàn vẹn byte tại thời điểm audit, không tự chứng minh chuẩn bị môi trường không thiên lệch. Báo cáo thống kê được đọc từ checkpoint sealed, không lấy số tổng của các pass cũ.

V1 của trình tổng hợp audit đã hiểu nhầm40 dòng historical NOT_ATTEMPTED có đường dẫn trống thành workspace, tạo40 missing-file flags giả. V2 tách chúng thành trạng thái không thực thi; không có raw file bị mất và không thay số liệu thực nghiệm. File classes300.* trung gian V2 chưa đọc đúng tên trường commit_sha; bảng bàn giao **class_history300.csv/json** đã lấy đúng commit_sha/focal source hash từ manifest và kiểm join. Không dùng trường source_commit trống của bản trung gian để kết luận thiếu provenance. Các bản trung gian được giữ, không xóa bằng chứng.

error_evidence.csv chứa các dòng khớp pattern để truy log, có thể có warning hoặc tên plugin bình thường; không đếm từng dòng thành lỗi. Nhãn lỗi terminal phải đọc cùng phase, exit/timeout, report và category mỗi class. Những thông báo minion TIMED_OUT trong294 chẳng hạn không biến class294 thành lifecycle failure.

'''
files=[('CLASS_HISTORY300.md','Bảng300 và lịch sử từng class, links từng receipt'),('class_history300.csv','Bảng300 đầy đủ: commit/source/seed/stages/scores/G0/E0/selection/attempt paths'),('command_attempts.csv','2195 command plans/receipts, argv, thời gian, logs và hashes'),('generated_without_valid_measurement32.csv','32 suite hoàn chỉnh chưa có PIT quan sát'),('generation_unsuccessful37.csv','37 class generation không hoàn thành'),('adapter_not_started10.csv','10 class bị chặn trước generation'),('repository_summary30.csv','Tổng hợp theo30 repositories'),('error_evidence.csv','Dòng log, line number và hash để truy nguyên'),('GENERATION_PROFILE_CHECKS.json','305 kiểm profile/seed/cap'),('RAW_PIT_RECHECK.json','221 report tính lại và class294'),('verified_input_hashes.json','Danh mục11.912 file đã kiểm'),('summary.json','Counters và phạm vi audit')]
md+=table(['File','Nội dung'],[[link(O/n),d] for n,d in files])
md+='\nTài liệu policy/provenance bổ sung (bản lịch sử có cutoff, không dùng số tổng cũ):\n\n'
for p in [H/'policy_timeline.csv',H/'dependency_selector_changes.csv',H/'verification.json',R/'completion_amendment_v1/POLICY.md',R/'completion_amendment_v1/STAGE_POLICY_ANNEX_V2.md',R/'completion_amendment_v1/MAVEN_POLICY_ANNEX.md',R/'completion_amendment_v1/PARTIAL_PIT_POLICY_V3.md',F/'statistics.json']:
 md+='- '+link(p)+'\n'
md+='\nCác artifact chỉ lưu riêng trong workspace. Không công khai code, không thêm URL, không ghi đè dữ liệu hay sửa paper trong audit này. Trạng thái tiến trình hiện tại và kiểm protected files nằm ở FINAL_INTEGRITY.json; checksum gói audit ở SHA256SUMS.txt.\n'
write('BAO_CAO_TOAN_BO_E1.md',md)
audit.log('E1_EXECUTION_REPORT_WRITTEN',path=str(O/'BAO_CAO_TOAN_BO_E1.md'),sha256=sha(O/'BAO_CAO_TOAN_BO_E1.md'),class_history_sha256=sha(O/'class_history300.csv'),new_experiments=0)
print(json.dumps({'report':str(O/'BAO_CAO_TOAN_BO_E1.md'),'classes':len(history),'repositories':len(repos),'report_bytes':(O/'BAO_CAO_TOAN_BO_E1.md').stat().st_size,'history_bytes':(O/'CLASS_HISTORY300.md').stat().st_size}))
