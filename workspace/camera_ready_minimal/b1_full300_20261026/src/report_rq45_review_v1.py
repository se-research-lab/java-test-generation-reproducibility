"""Write traceable author report and current reviewer responses, without reruns."""
import json,re,sys
from pathlib import Path
from collections import Counter
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';O=R/'analysis_camera_ready_rq45_v1'
sys.path.insert(0,str(B));import audit
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
a=read(O/'analysis.json');rows=read(O/'class_evidence300.json')
subtypes=[]
for row in rows:
    if row['E1_category']!='GENERATION_UNSUCCESSFUL':continue
    folder=Path(row['E1_result_path']).parent;attempts=[]
    for plan in sorted((folder/'commands').glob('*/plan.json')):
        if '-jar' not in read(plan)['argv'] or not (plan.parent/'started.json').exists():continue
        finish=read(plan.parent/'finished.json');paths=[plan.parent/n for n in ('stdout.txt','stderr.txt')]
        text='\n'.join(p.read_text(encoding='utf-8',errors='replace') for p in paths)
        flags=[n for n,pattern in [('UNSUPPORTED_BYTECODE','Unsupported class file major version'),('SERVICE_PROVIDER_TYPE','ServiceConfigurationError'),('MALFORMED_GENERIC_TYPE','MalformedParameterizedTypeException'),('STACK_OVERFLOW','StackOverflowError'),('SIZE_MISMATCH','Size mismatched')] if pattern in text]
        if finish.get('reason')=='TIMEOUT':flags.append('TIMEOUT')
        attempts.append({'command':plan.parent.name,'flags':flags,'returncode':finish['returncode'],'reason':finish.get('reason'),'logs':{str(p):audit.sha(p) for p in paths}})
    subtypes.append({'index':row['index'],'attempts':attempts,'final_attempt_flags':attempts[-1]['flags'] if attempts else [],'interpretation':'observed symptoms; not proven sole cause'})
(O/'maven_generation_failure_details27.json').write_text(json.dumps(subtypes,indent=2),encoding='utf-8')
subcounts=Counter(f for r in subtypes for f in set(r['final_attempt_flags']))
md='''# Hệ thống lỗi GPT/EvoSuite và cập nhật RQ4–RQ5

## Kết luận cần dùng trong camera-ready

Giữ nguyên năm RQ và dữ liệu GPT RQ1–RQ3 (61/45/300). Giữ E0 toàn300 là kết quả lịch sử của cấu hình assertions=false. E1 là bổ sung assertions/runtime và hỗ trợ tích hợp riêng; không được mô tả như chỉ thay một cờ assertions.

**RQ4:** chỉ còn kết luận NI có điều kiện cho E0. Fixed49 E1 không xác lập thứ tự trung bình ổn định, còn extension E1 có hướng chênh lệch rõ về phía E1 dưới pipeline đang đo. Không chuyển NI E0 thành NI E1, không suy diễn mean-bound là kiểm định signed-rank, không chỉnh điểm để giữ kết luận cũ.

**RQ5:** hướng EvoSuite có nhiều process-build thành công hơn vẫn giữ, nhưng là so sánh pipeline được hỗ trợ môi trường khác nhau. 204 là số gate pass quan sát, không phải 204 suite đều pass assertions hay tỷ lệ nghiệm thu full300.

## 1. GPT và E0: giữ taxonomy lịch sử, bổ sung log theo đúng nhánh

| Stage ghi trong metrics gốc | GPT G0 | EvoSuite E0 |
|---|---:|---:|
| ok (legacy process gate) | 61 | 158 |
| agone runtime failure | 1 | 90 |
| generated-test compilation failure | 158 | 32 |
| generated-test runtime failure | 2 | 2 |
| Gradle verification failure | 7 | 0 |
| JaCoCo failure | 24 | 0 |
| Maven reactor prewarm failure | 2 | 2 |
| Maven verification failure | 43 | 15 |
| Maven verification timeout | 1 | 0 |
| PIT failure | 1 | 1 |
| Tổng | 300 | 300 |

Đã tách 298 log từng nhánh bằng STARTING treatment marker; hai lớp prewarm không có lượt GPT. Mỗi đoạn giữ đường dẫn, số dòng và SHA-256. Không dùng đoạn lỗi GPT nằm cuối log chung để giải thích EvoSuite.

Trong các hàng GPT fail, log riêng nhánh có: 106 unresolved-symbol, 41 type/signature, 21 missing-package, 20 access-control, 17 syntax/duplicate, 22 artifact/plugin-resolution và 11 license-header. Các dấu hiệu **chồng lấp**, không cộng thành tổng thất bại. 156/158 compile-labelled rows có vị trí source generated test; 2 không có marker vị trí đó. Marker ở source chỉ định nơi báo lỗi, chưa chứng minh lỗi hoàn toàn do model: dependency và phiên bản API vẫn có thể góp phần. Một hàng có production-source/dependency error. Tránh câu “GPT sinh sai 158 test” hoặc gọi 24 JaCoCo labels là 24 lỗi riêng của JaCoCo đã được chứng minh.

Log E0 riêng nhánh xác nhận lỗi biến project_df_evosuite chưa được gán ở 20/40 class Gradle. Không suy rộng thành nguyên nhân của cả40. Trong 32 compile-labelled E0 rows, chỉ18 có marker vị trí generated test ở chính nhánh E0; đây là cảnh báo attribution, không phải cơ sở tự sửa metric gốc.

## 2. E1 toàn bộ 300 slot: đếm class, không đếm attempts

| Nhóm loại trừ lẫn nhau | Số class |
|---|---:|
| Qua process gate: Maven195 + Gradle9 | 204 |
| Không sinh suite hoàn chỉnh: Maven27 + Gradle10 | 37 |
| Chưa gọi EvoSuite vì thiếu task Gradle | 10 |
| Có suite, fail license-header check | 8 |
| Có suite, fail PIT coverage minion | 10 |
| Có suite, compile được nhưng test runtime fail | 1 |
| Chưa chấm: POM không parse được | 10 |
| Chưa chấm: JUnit3 guard, đã sinh suite | 10 |
| Chưa chấm: PIT dependency Gradle, đã sinh suite | 10 |
| Tổng | 300 |

Có243 class tạo đủ native suite:204 gate pass,19 fail measurement lifecycle và20 chưa đo. Trong19, chỉ #175 có bằng chứng test execution fail (NullPointerException ở test0); 8 license và10 PIT không phải19 Java compile errors. 13/18 failure Maven có suite đã pass theo audit. Trong204 gate pass có6 thiếu complete suite evidence và16 thiếu complete measurement evidence; không lấy gate làm chứng nhận assertions.

Gradle40:9 pass;10 missing-task trước generation;3 class-loading;6 unsupported-bytecode;1 timeout;1 test-runtime fail;10 PIT dependency unscored. Không sửa config hoặc test sau lỗi. Maven27 được chia dấu hiệu theo từng attempt trong maven_generation_failure_details27.json; retry kỹ thuật đã khóa vẫn khác chẩn đoán sau lỗi. Timeout không được retry theo điểm.

## 3. RQ4: các phạm vi phải ghi đúng denominator

| Phạm vi | n | GPT mean | Evo mean | Mean GPT−E (pp) | GPT cao / E cao / hòa |
|---|---:|---:|---:|---:|---|
| E0 lịch sử toàn300 | 300 | 11,86 | 7,01 | +4,84 | 46 / 70 / 184 |
| E1 fixed49 lịch sử | 49 | 58,44 | 59,16 | −0,72 | 14 / 26 / 9 |
| E1 có raw outcome | 270 | 11,35 | 31,65 | −20,31 | 16 / 149 / 105 |

Bootstrap toàn repository,20.000 draws,seed20261023: fixed49 gap CI95=[−7,50;8,38] (15repo); observed270=[−26,90;−13,94] (27repo). Đây là exploratory mean intervals, không phải NI hoặc within-run variance. 270 không có cùng denominator với300; không so mean GPT11,35 ở đây với mean GPT11,86 toàn300 như thể GPT đã đổi kết quả.

Giữ đủ denominator300 và cho30 unscored E1 score chạy từ0 đến100: mean-gap bounds=[−26,63;−16,63]pp. Nếu10 missing-task raw zeros cũng xem là unresolved thì=[−29,96;−16,63]pp. Đây là **giới hạn xác định theo dữ liệu còn lại**, không phải CI, không tự gán0 vào30 hàng và không chứng minh signed-rank inferiority. Nếu đồng thời xem class003 hậu kiểm là unresolved thì41unknown cho bounds=[−29,96;−16,30]pp. Hướng mean vẫn nghiêng E1 trong các giả định đó; những kết quả quan sát khác vẫn chịu giới hạn gate và hỗ trợ môi trường.

Giao G0–E1 mới có55class, mean gap−4,73pp,CI95=[−18,86;8,51]. Chỉ dùng chẩn đoán trong artifact; không thay fixed49,61/45/300 hoặc chọn theo kết quả tốt.

## 4. RQ5: giữ pipeline gate, không dựng thêm thang đo

E0 toàn300: GPT61,E0158; both49,G-only12,E-only109,neither130. Maven-only260:51/158 vẫn giữ kết luận pipeline E0 advantage; Gradle10/0 là lỗi tích hợp lịch sử, không phải thuộc tính công cụ.

E1 observed270: GPT56,E1204; both55,G-only1,E-only149,neither65. 30 unscored chứa5 GPT builds đã biết, nên **GPT vẫn61/300**. Build bounds E1=[204,234]/300=[68,78]%; nếu10 missing-task cũng unresolved thì=[204,244]/300=[68,81,33]%. Không trình bày204/300 như tỷ lệ thành công đầy đủ đã nghiệm thu.

Class003 được map sang một diagnostic thành công sau khi đã biết outcome: không thể gọi selection hoàn toàn outcome-blind. Dùng raw outcome gốc cho riêng sensitivity làm204→203 và mean-gap−20,31→−19,94, không đổi hướng mô tả. Không sửa map hay raw để tạo sensitivity này. Hạn chế này phải có trong Methods/Threats; bỏ nó sẽ làm người đọc hiểu sai thiết kế.

## 5. Phạm vi chỉnh bài và điều không nên làm

- Đã thêm Table6 phân loại E1; Table4 giữ nhãn G0/E0; Abstract,Methods,Results4.6,Discussion,Threats,Conclusion phản ánh E1.
- Giữ nguyên năm câu RQ; bảng lịch sử RQ1–RQ3 và Table3 denominator; fixed49 không thay bằng55.
- Không sinh/đo lại, sửa test, nâng dependency, đổi selector/seed hoặc loại class để cứu kết luận. Không ghép kết quả repeated dang dở.
- Không gọi270 outcomes là E1 full300 complete; không gọi mọi raw zero là generator failure. Không nói E1 cô lập hiệu ứng assertions.
- R2.1 partial; thực nghiệm còn missing và sai khác tích hợp. Margin justification,repeated-run,equalized budgets,hybrid evaluation vẫn chưa hoàn tất.
- Bản thảo riêng15trang; sáu tác giả,Le Thi Quynh Chi corresponding duy nhất. Giữ nguyên câu supplementary-only theo yêu cầu tác giả,không công khai code/URL.

## 6. Cần tác giả kiểm trước nộp

Chấp nhận cách diễn giải RQ4 thu hẹp theo bằng chứng; kiểm policy/diagnostic caveat, tính chính xác tài trợ và metadata, receipt supplementary, đăng ký/license trong Confy+. Chưa upload/ký/thanh toán. Hướng dẫn hội nghị: https://fisat.eai-conferences.org/2026/camera-ready-instructions/. PDF+source ZIP là gói manuscript riêng, không chứa code thực nghiệm. Theo yêu cầu tác giả, không thêm đoạn AI-use vào manuscript; cũng không chứng nhận rằng công việc chỉ là copy-editing hoặc đã đáp ứng phần khai báo chính sách.

## 7. Tái lập phân tích và bằng chứng

analysis.json chứa mọi số liệu/CI/bounds; class_evidence300.json nối G0/E0/E1 bằng class_key; historical_arm_scoped_evidence600.json chứa nhãn gốc, marker theo nhánh, số dòng và hash; input_hashes.json khóa các đầu vào; source_change_manifest.json và backup lưu bản trước sửa. Script phân tích chỉ đọc các kết quả có sẵn. Không thay raw result hoặc paper gốc.
'''
md+='\nDấu hiệu trên attempt cuối của27 Maven generation failures (có thể chồng lấp): '+json.dumps(dict(subcounts),ensure_ascii=False)+'.\n'
(O/'BAO_CAO_LOI_VA_DIEU_CHINH_RQ45.md').write_text(md,encoding='utf-8')

items=[
('R1.1','Addressed with gate qualification','Sections3.3–3.5,4.3,4.6;pp.5–7,8–11','The original gate and strict score are retained. Execution/report flags accompany scores and do not create a replacement measurement scale.'),
('R1.2','Addressed: fixed-cohort descriptive analysis','Sections4.4–4.5;pp.9–10;Table5','The original49 keys across15 Maven repositories remain fixed. G0/E0 means58.44/17.63%; G0/E1 means58.44/59.16%; E1 paired gap−0.72pp,repository-bootstrap interval[−7.50,8.38]. The new55-key intersection is diagnostic only.'),
('R1.3','Partial: additional E1, not a validated replacement full300 NI test','Abstract;Sections3.5,4.5–4.6;pp.1,6–7,10–11','E1 enables MUTATION assertions,scaffolding and runtime. It has270 recorded outcomes and30 unscored classes. Runtime support,seeds and integration also differ, so this is not an assertion-only causal comparison.'),
('R1.4','Addressed by narrower interpretation','Table2;Sections4.2,5;pp.8,11–12','The184 historical ties include130 joint build failures. They describe pipeline usability,not equal oracle quality. NI remains E0-specific.'),
('R1.5','Open: practical margin not validated','Section3.4 and Discussion;pp.6,12','The5-point margin is an author-selected working tolerance informed by literature context. We do not claim that AgoneTest validates this NI threshold or stakeholder acceptability.'),
('R1.6','Partial: inference narrowed; reference uncertainty remains','Sections2.1,3.5;pp.3,7','The44.5% published aggregate is a fixed reference,not a known population median. Inconsistent denominator descriptions and unavailable source uncertainty preclude a formal between-study replication inference.'),
('R1.7','Open: no complete repeated-run evaluation','Section6;pp.12–13','One scheduled run per configuration/class remains. Technical retries and repository bootstrap do not estimate within-class generation variance. Incomplete repeated data are excluded.'),
('R1.8','Addressed through pipeline qualification and sensitivity','Sections4.3,4.6;pp.8–11;Tables4,6','Historical Maven-only build counts51/260 G0 and158/260 E0 retain the pipeline advantage. Gradle E1 records9 passes but unresolved integration persists. Buildability is not attributed solely to the generator.'),
('R1.9','Addressed: no-API failures distinct','Sections3.3,4.1,4.3;pp.5,7–9','Two prewarm failures have no GPT generation. They remain in the historical strict denominator300 and are not model-generation failures.'),
('R1.10','Partial: analytical pre-pilot lock unverified','Sections3.1–3.2,3.4,6;pp.3–6,12','We distinguish the recorded pre-merge protocol from an unverified lock before inspecting pilot outcomes. The n≥60 rule is described as recorded,not proven prospectively prespecified.'),
('R1.11','Partial: fixed49 certified; broader report limitations explicit','Section4.5;pp.10','Fixed49 focal counts range1–47,median17,mean20.20. Percentages and absolute counts are distinct; complete certified historical denominator inventories are not claimed.'),
('R1.12','Addressed through paired supplement and narrowed claims','Abstract;Sections4.4–7;pp.1,9–13','The fixed49 paired analysis and assertion-enabled sensitivity are included. E0 NI is not generalized to E1 or to generator quality independent of integration.'),
('R2.strengths','Acknowledged with provenance limits','Sections3–4;pp.3–11','Original keys,G0 observations and historical calculations remain. New policy timing and outcome selection exceptions are disclosed rather than extending historical protocol claims to E1.'),
('R2.1','PARTIAL; not fully resolved','Sections3.5,4.5–4.6,5–7;pp.6–7,10–13','Assertion-enabled native generation has been extended across all300 slots,with49 reused and251 additional slots processed. There are270 raw outcomes,30 unscored,and environment/post-outcome-selection limitations. On270 observed keys means are11.35% G0 and31.65% E1,not evidence supporting transfer of E0 NI. We do not describe E1 as a complete validated300-pair replacement.'),
('R2.2','Maven alternative addressed; Gradle repair only partial','Sections4.3,4.6;pp.8–11','The reviewer-offered Maven260 sensitivity is retained. The frozen Gradle40 batch records9 pass,1 test execution failure,10 generation failures,10 missing-task failures and10 unscored PIT-dependency cases. Remaining failures are not silently repaired or scored as generator faults.'),
('R2.3','Addressed: scopes separated','Sections4.2,4.4–4.6;pp.8–11','Historical300, fixed49 and observed270 are explicitly different cohorts. Thirty missing E1 outcomes are not zero-filled; fixed300 bounds are reported separately and are not NI tests.'),
('R2.4','Addressed','Abstract;Table2;Discussion;pp.1,8,12','We retain the+4.84pp historical mean gap alongside46/70/184 directions and A12=0.443. A12 uses cross-arm combinations; NI effects concern margin-shifted differences.'),
('R2.5','Open: no complete repeated-run evaluation','Sections5–6;pp.12–13','No completed within-class repeated evaluation is reported; incomplete data are excluded. Configuration changes and cluster resampling are not replacements for repeated generation.'),
('R2.6','Addressed as exploratory sensitivity','Sections3.5,4.4–4.6;pp.6–7,9–11','Whole repositories are resampled20,000 times with seed20261023. Historical300 uses30 repositories,fixed49 uses15,and observed270 uses27. The observed-E1 mean-gap interval[−26.90,−13.94] is conditional on available outcomes and cannot remove nonrandom missingness or policy-selection limitations.'),
('R2.7','Addressed','Abstract;Table2;Conclusion;pp.1,8,13','GPT build rate61/300=20.33% remains8.27pp below28.6%;Wilson interval[16.17,25.25]%. G0 scores and cohorts61/45/300 are unchanged.'),
('R2.minor','Addressed with evidence qualification','Section4.3/Table4;Section4.6/Table6;pp.8–11','Table4 reports all historical stages. Table6 partitions E1 slots. Arm-scoped log markers reveal overlapping compilation,API,dependency,license and integration symptoms; recorded labels are not treated as proven exclusive causes.'),
('R2.path','Partial overall','Sections4.3–7;pp.8–13','The revision includes fixed49, E1 extension, full300 missing-outcome bounds, Maven sensitivity and clustering. Full E1 measurement validity,repeated variance and budget equality remain incomplete.'),
('R3.1','Additional configuration evaluated; scope limitations retained','Sections3.5,4.5–4.6;pp.6–7,10–11','E1 enables assertions/runtime but keeps other nondefault settings explicit. Its incomplete extension is described as operational sensitivity,not default-EvoSuite superiority or a uniform controlled intervention.'),
('R3.2','Open: budgets documented, not equalized','Sections3.3,3.5,5;pp.5–7,12','The GPT2048-token cap and EvoSuite60-second search are different budgets. Generation caps and measurement caps are stated; equal compute/cost is not claimed.'),
('R3.3','Addressed as sensitivity','Sections3.5,4.4–4.6;pp.6–7,9–11','Repository-bootstrap analyses preserve within-repository observations and pairing. They supplement rather than retroactively replace historical inference.'),
('R3.4','Partial: detailed diagnosis, remaining integration limitations','Sections4.3,4.6 and6;pp.8–12;Tables4,6','Logs are split by arm before attribution. E0 has20 observed Gradle copy-variable errors. E1 separates missing task,classpath/bytecode,generation timeout,license,PIT and actual test execution failure. Remaining missingness and runtime asymmetry are disclosed.'),
('R3.5','Not evaluated; future work','Section2.2 and Discussion;pp.3,12','Repair/context-enhanced GPT and hybrid approaches are separate treatments and remain unevaluated. The zero-shot GPT arm was not changed.'),
]
response=['# Response to Reviewers — RQ4/RQ5 Evidence Revision','',
 'This response accompanies the separate 15-page manuscript draft, including references. It supersedes the earlier response for this draft only. No upload, registration, payment or license signature has been performed.', '',
 'The five research questions and archived GPT observations remain unchanged. E0 denotes the historical assertion-disabled baseline. E1 denotes the assertion-enabled configuration with documented runtime/integration support and policy timing. The fixed49 analysis remains intact; the extension has270 operational outcomes and30 unscored classes. It is not a fully validated assertion-enabled300-pair NI experiment. No incomplete repeated-run observations enter the paper.', '']
statuses={}
for key,status,loc,body in items:
    # Space adjacent numbers/words for readable response prose.
    body=re.sub(r'(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])',' ',body)
    loc=loc.replace(';pp.','; pp.').replace('Sections3','Sections 3').replace('Sections4','Sections 4').replace('Sections5','Sections 5').replace('Section3','Section 3').replace('Section4','Section 4').replace('Section6','Section 6').replace('Section2','Section 2').replace('Table2','Table 2').replace('Table4','Table 4').replace('Table5','Table 5').replace('Table6','Table 6')
    response += [f'## {key}', '', f'**Status:** {status}.', '', f'**Location:** {loc}.', '', body, '']
    statuses[key]={'status':status,'location':loc}
response+=['## Remaining scope', '', 'R2.1, practical margin validation, complete repeated-run evaluation, equalized budgets and hybrid evaluation are not marked fully resolved. All raw attempts are retained; one Maven diagnostic selection occurred after its outcome was known and is disclosed with an original-outcome sensitivity. No experimental test repair or policy adjustment was made during this offline revision. Private supplementary availability wording is retained, with no invented public URL.']
(O/'RESPONSE_TO_REVIEWERS.md').write_text('\n'.join(response)+'\n',encoding='utf-8')
(O/'REVIEWER_STATUS.json').write_text(json.dumps(statuses,ensure_ascii=False,indent=2),encoding='utf-8')
audit.log('B1_RQ45_AUTHOR_REPORT_AND_RESPONSE',report_sha256=audit.sha(O/'BAO_CAO_LOI_VA_DIEU_CHINH_RQ45.md'),response_sha256=audit.sha(O/'RESPONSE_TO_REVIEWERS.md'),status_sha256=audit.sha(O/'REVIEWER_STATUS.json'),experiment_calls=0)
print(json.dumps({'maven27_final_attempt_symptoms':dict(subcounts),'reviewer_items':len(items)},indent=2))
