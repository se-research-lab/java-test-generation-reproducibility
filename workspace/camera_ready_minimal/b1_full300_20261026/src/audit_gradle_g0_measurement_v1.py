"""Read historical Gradle evidence; no generation, remeasurement or score edits."""
import csv,hashlib,json,sys,shutil
from collections import Counter
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def signature(rows):return hashlib.sha256(json.dumps(sorted(tuple(r[:5]) for r in rows),ensure_ascii=False,separators=(',',':')).encode('utf-8')).hexdigest()
root=R.parents[1];metrics=root/'scripts_v2/results/runs/full300_merged_20260724_paper/metrics_wide.csv'
with metrics.open(encoding='utf-8-sig',newline='') as f:allrows=list(csv.DictReader(f))
gradle=[r for r in allrows if r['build_tool'].lower()=='gradle'];built=[r for r in gradle if r['gpt_compilation']=='1'];assert len(gradle)==40 and len(built)==10
manifest={j['class_key']:j for j in load(R/'manifest300.json')};contexts={j['class_key']:j for j in load(R/'inputs/context251_v1/manifest.json')}
out=R/'audit/gradle_g0_measurement_v1';out.mkdir(exist_ok=False);(out/'raw').mkdir();results=[]
audit.verify()
for row in built:
 j=manifest[row['class_key']];ctx=contexts[row['class_key']];index=j['sample_index_1based'];selected=Path(ctx['prior_synthesized_test_relative']).stem
 reports=Path(j['source_candidate']['source_repo'])/j['module']/'build/reports/pitest';candidates=[]
 for report in sorted(reports.rglob('mutations.csv')) if reports.exists() else []:
  data=report.read_bytes();h=hashlib.sha256(data).hexdigest();dest=out/'raw'/f'{index:03d}_{h}.csv'
  if not dest.exists():
   with dest.open('xb') as f:f.write(data)
  assert sha(dest)==h and sha(report)==h
  with dest.open(encoding='utf-8-sig',newline='') as f:raw=list(csv.reader(f))
  assert all(len(r)==7 for r in raw),'Malformed historical PIT CSV'
  focal=[r for r in raw if r[0].removesuffix('.java')==j['focal_class'] and (r[1].rsplit('.',1)[0] if '.' in r[1] else '')==ctx['package']]
  killed=[r for r in focal if r[5]=='KILLED'];foreign=[r[6] for r in killed if selected not in r[6]]
  owner=bool(killed) and not foreign and all(selected in r[6] for r in killed)
  score=round(100*len(killed)/len(focal),2) if focal else None
  candidates.append({'source':str(report),'source_sha256':h,'backup':dest.relative_to(R).as_posix(),'focal_mutants':len(focal),'killed':len(killed),'raw_percent':score,'archived_percent_matches':score is not None and abs(score-float(row['gpt_mutation_coverage']))<0.011,'G0_owner_confirmed_by_killing_test':owner,'ownership_limit':'No positive killing-test reference cannot prove ownership from CSV alone' if not owner else None,'foreign_killing_tests':foreign,'observable_universe_sha256_excluding_status':signature(focal),'observable_universe_fields':'SourceFile, mutatedClass, mutator, method, line; multiplicity retained; CSV cannot identify finer bytecode site','mutators_observed':dict(Counter(r[2] for r in focal)),'mutated_classes':sorted({r[1] for r in focal}),'engine_version_from_CSV':None})
 results.append({'sample_index_1based':index,'class_key':j['class_key'],'repo_id':j['repo_id'],'frozen_G0_build':1,'frozen_G0_mutation_percent':row['gpt_mutation_coverage'],'selected_G0_test':selected,'candidates':candidates,'unique_owner_confirmed_report':len([c for c in candidates if c['G0_owner_confirmed_by_killing_test']])==1})
summary={'status':'READ_ONLY_HISTORICAL_EVIDENCE_AUDIT','Gradle_total':40,'G0_build_success':10,'G0_build_by_repository':dict(Counter(r['repo_id'] for r in built)),'rows':results,'metrics_sha256':sha(metrics),'measurement_scope_rule':'Preserve legacy Gradle exact focal FQCN target; do not expand to nested targets merely to resemble Maven. Compare observable mutant universe where historical owner evidence exists; never alter G0 scores/cohorts. Engine effective version needs evidence beyond CSV.','new_generation_calls':0,'new_measurements':0,'GPT_API_calls':0}
dump(out/'result.json',summary)
lines=['# Đối chiếu đo lường GPT gốc trên Gradle','', 'Chỉ đọc bằng chứng lịch sử; không chạy lại GPT hoặc PIT. Có40 class Gradle,10 class GPT build thành công:5 thuộc41627638,4 thuộc74999474,1 thuộc85795396. D2 không có GPT build thành công trong bảng gốc.','', '|Index gốc|Repo|Điểm G0 giữ nguyên|Số PIT CSV tìm thấy|Có đúng một report xác nhận owner G0 bằng killing test|','|---|---|---:|---:|---|']
lines += [f"|{r['sample_index_1based']}|{r['repo_id']}|{r['frozen_G0_mutation_percent']}|{len(r['candidates'])}|{r['unique_owner_confirmed_report']}|" for r in results]
lines += ['', 'PIT CSV không ghi engine version. Mapping plugin/engine trong prototype chưa được xem là phiên bản runtime GPT đã chứng minh. Report không có killing test dương tính chưa đủ xác nhận owner chỉ từCSV; không bịa bằng chứng hoặc chọn report có điểm thuận lợi.', '', 'Trước benchmark Gradle E1: giữ legacy targetClasses bằng đúng FQCN focal; không tự thêm nested target vì reviewer chỉ yêu cầu oracles/scaffolding và sửa path/harness. E49 Maven tiếp tục policy của Maven đã nghiệm thu. Cùng một cặp class cần giữ miền mutant của measurement gốc; không bắt hai build system có số mutant như nhau.', '', 'Với raw report G0 đã xác nhận, có thể đối chiếu multiset SourceFile/class/mutator/method/line và multiplicity, bỏ trạng thái KILLED khỏi chữ ký. Đây là kiểm miền mutant quan sát được, không thay metric hoặc chọn theo score; CSV không chứng minh đồng nhất bytecode site đầy đủ. Không thay giá trị G0 hoặc dùng một tập giao mới thay mẫu RQ1–RQ3.', '', 'Cần kiểm engine/agent/mutators thực tế, resource/JVM/ignoreFailures/enabled của task và nguyên nhân thiếu report trước khi chấp thuận Gradle40. Nếu thiếu bằng chứng, giữ trạng thái chưa qualify; không tự nâng version, rerun GPT hoặc quy failure của harness cho generator.']
with (out/'REPORT.md').open('x',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
audit.verify();audit.log('B1_GRADLE_G0_MEASUREMENT_AUDITED',result_sha256=sha(out/'result.json'),report_sha256=sha(out/'REPORT.md'),new_experiment_calls=0,GPT_API_calls=0)
print(json.dumps({'Gradle40':40,'G0_build10':10,'owner_confirmed_rows':sum(r['unique_owner_confirmed_report'] for r in results),'new_experiment_calls':0},indent=2))
