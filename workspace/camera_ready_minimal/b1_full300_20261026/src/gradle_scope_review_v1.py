"""Read Gradle descriptors and historical context only; no wrapper/Gradle execution."""
import json,re,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(p.read_text(encoding='utf-8'))
jobs=[j for j in load(R/'manifest300.json') if j['build_tool']=='gradle'];contexts={j['class_key']:j for j in load(R/'inputs/context251_v1/manifest.json')};out=R/'audit/gradle_scope_review_v1';out.mkdir(exist_ok=False);repos={}
for j in jobs:
 root=Path(j['source_candidate']['source_repo']);context=contexts[j['class_key']]
 r=repos.setdefault(j['repo_id'],{'repo_id':j['repo_id'],'classes':[],'wrapper_versions':set(),'frameworks':set(),'descriptor_evidence':{},'status':'NOT_EXECUTION_QUALIFIED'})
 r['classes'].append({'sample_index':j['sample_index_1based'],'class_key':j['class_key'],'module':j['module']})
 r['frameworks'].add((str(context['junit_version']),str(context['testng_version'])))
 paths=[root/'build.gradle',root/'build.gradle.kts',root/'settings.gradle',root/'settings.gradle.kts',root/'gradle/wrapper/gradle-wrapper.properties',root/j['module']/'build.gradle',root/j['module']/'build.gradle.kts']
 for p in paths:
  if not p.is_file():continue
  h=audit.sha(p);key=p.relative_to(root).as_posix()+'#'+h
  if key in r['descriptor_evidence']:continue
  text=p.read_text(encoding='utf-8',errors='replace');m=re.search(r'gradle-([\d.]+)-(?:bin|all)\.zip',text)
  if m:r['wrapper_versions'].add(m.group(1))
  markers={name:bool(re.search(pattern,text,re.I)) for name,pattern in {'useTestNG':r'\buseTestNG\s*\(','useJUnit':r'\buseJUnit\s*\(','JUnitPlatform':r'\buseJUnitPlatform\s*\(','pitest':r'\bpitest\b','jacoco':r'\bjacoco\b','EvoSuite_runtime':r'evosuite-standalone-runtime','testImplementation':r'\btestImplementation\b','testCompile':r'\btestCompile\b','custom_buildDir':r'\bbuildDir\s*='}.items()}
  r['descriptor_evidence'][key]={'relative':p.relative_to(root).as_posix(),'source_path':str(p),'sha256':h,'markers':markers,'gradle_wrapper_version':m.group(1) if m else None}
for r in repos.values():r['wrapper_versions']=sorted(r['wrapper_versions']);r['frameworks']=[{'junit':x,'testng':y} for x,y in sorted(r['frameworks'])]
report={'n':len(jobs),'repositories':list(repos.values()),'original_gradleLib_sha256':audit.sha(R.parents[1]/'scripts_v2/AgoneTest/gradleLib.py'),'experiment_calls':0,'qualification':'not yet executed','gate_issue':'Historical Gradle test+JaCoCo success returns build=True even if PIT later fails; cannot silently apply Maven literal BUILD SUCCESS gate to Gradle. Separate build/report evidence and declare gate mapping before admission.','timeout_issue':'Historical Gradle PIT default900s differs from proposed uniform300s. Timeout policy needs explicit scope decision before running Gradle, not outcome-dependent retuning.'}
with (out/'report.json').open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
lines=['# Gradle40 — kiểm phạm vi trước execution','','Đọc descriptor và metadata lịch sử, chưa chạy Gradle. Có4 repository,10class/repository.','','| Repo | Wrapper trong source | Framework metadata (JUnit / TestNG) | Trạng thái |','|---|---|---|---|']
for r in repos.values():lines.append('| '+r['repo_id']+' | '+', '.join(r['wrapper_versions'])+' | '+'; '.join(x['junit']+' / '+x['testng'] for x in r['frameworks'])+' | Chưa qualify |')
lines+=['','## Những điểm phải khóa rõ','',
'- Classpath generation cũ chỉ lấy thư mục main classes; cần resolved dependency classpath trong sandbox EvoSuite. Không sửa dependency nghiệp vụ để che lỗi resolve.',
'- Runtime cũ được chèn bằng implementation; adapter mới dự kiến dùng test scope và cần chọn API tương thích wrapper, không giả định mọi project có testImplementation.',
'- Native EvoSuite là JUnit4. Với TestNG/JUnitPlatform, phải kiểm discovery bằng testcase XML và giữ cấu hình GPT nguyên vẹn.',
'- Gate Gradle cũ khác Maven: test+JaCoCo có thể đạt trong khi PIT thất bại; không tự thay bằng điều kiện all-tasks-success. Điểm mutation chưa có report vẫn theo policy đã khai báo.',
'- PIT timeout Gradle cũ mặc định900s, trong khi kế hoạch B1 ghi300s tổng quát. Đây là điểm chưa đủ bằng chứng để gọi E1 là chỉ đổi assertions. Chưa admit Gradle; phải chốt timeout và cách báo khác biệt trước khi có kết quả mới.',
'- Maven260 sensitivity vẫn bắt buộc có, kể cả khi Gradle40 cuối cùng chạy được. Không gán0 cho class chưa thử hoặc chỉ đang blocked.',
'','## Đề xuất để giữ đúng phạm vi','',
'Cho nhánh Maven tiếp tục qualification riêng theo E49; giữ Gradle ở trạng thái chưa admit. Trước execution Gradle, lập protocol mapping riêng cho build gate, PIT timeout, wrapper/JDK, classpath và test discovery, kèm lý do reviewer R2.2. Không sử dụng lại kết quả E0 như E1. Không tự sửa protocol.json đã khóa hoặc thay bản paper.']
(out/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
audit.log('B1_GRADLE_SCOPE_REVIEW',n=40,report_sha256=audit.sha(out/'report.json'),execution_qualified=False)
print(json.dumps({'n':40,'repos':[{k:r[k] for k in ['repo_id','wrapper_versions','frameworks','status']} for r in repos.values()],'new_experiment_calls':0},indent=2))
