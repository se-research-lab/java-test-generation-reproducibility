"""Bind the four historical zero scores using saved execution evidence only."""
import csv,hashlib,json,re,sys
from pathlib import Path
from collections import Counter
from xml.etree import ElementTree as ET
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def preserve(source,folder):
 h=sha(source);dest=folder/(source.stem+'_'+h+source.suffix)
 if not dest.exists():
  with dest.open('xb') as f:f.write(source.read_bytes())
 assert sha(dest)==h
 return {'source':str(source),'source_sha256':h,'backup':dest.relative_to(R).as_posix()}
original=load(R/'audit/gradle_g0_measurement_v1/result.json');jobs={j['class_key']:j for j in load(R/'manifest300.json')};contexts={j['class_key']:j for j in load(R/'inputs/context251_v1/manifest.json')}
out=R/'audit/gradle_g0_zero_provenance_v2';out.mkdir(exist_ok=False);rows=[];audit.verify()
for old in original['rows']:
 if old['unique_owner_confirmed_report']:continue
 j=jobs[old['class_key']];ctx=contexts[old['class_key']];index=j['sample_index_1based'];folder=out/f'{index:03d}';folder.mkdir();selected=old['selected_G0_test']
 module=Path(j['source_candidate']['source_repo'])/j['module'];xmls=[]
 for path in sorted((module/'build/test-results').rglob('TEST-*.xml')):
  root=ET.parse(path).getroot();cases=root.findall('.//testcase')
  matching=[c for c in cases if c.get('classname','').rsplit('.',1)[-1]==selected]
  if not matching:continue
  xmls.append({**preserve(path,folder),'matched_cases':len(matching),'all_cases_selected':len(matching)==len(cases),'errors':sum(len(c.findall('failure'))+len(c.findall('error')) for c in matching),'skipped':sum(len(c.findall('skipped')) for c in matching),'case_names':[c.get('name') for c in matching]})
 metadata_source=next(r for r in ctx['metadata_sources'] if Path(r['path']).name=='project_info.json')
 sandbox=Path(metadata_source['path']).parent.parent;run_id=sandbox.parent.name;prefix=sandbox.name.split('_')[0]
 log=R.parents[1]/'scripts_v2/results/runs'/run_id/'class_logs'/f"{prefix}_{j['repo_id']}_{j['focal_class']}.stdout.log"
 logproof={'path':str(log),'exists':log.is_file()}
 if log.is_file():
  text=log.read_text(encoding='utf-8',errors='replace');marker='--//loading gradle execution..//';start='STARTING gpt-4o-mini-2024-07-18 test type'
  logproof.update(sha256=sha(log),Gradle_measurement_markers=text.count(marker),E0_scaffolding_move_failed='while trying to move the scaffolding file' in text,one_measurement_after_GPT_start=text.count(marker)==1 and start in text and text.index(marker)>text.index(start),selected_G0_test_mentioned=selected in text,package_command_completed='Package command completed' in text)
  keep=[{'line':i+1,'text':line} for i,line in enumerate(text.splitlines()) if any(token in line for token in ['STARTING evosuite test type',start,marker,'while trying to move the scaffolding file','Test classes:','Package command completed'])]
  dump(folder/'execution_markers.json',keep);logproof['extracted_markers']=str((folder/'execution_markers.json').relative_to(R))
 jacoco=[]
 for path in sorted((module/'build/reports/jacoco').rglob('*.csv')):
  with path.open(encoding='utf-8-sig',newline='') as f:focal=[r for r in csv.DictReader(f) if r.get('CLASS')==j['focal_class'] and r.get('PACKAGE','').replace('/','.')==ctx['package']]
  if focal:jacoco.append({**preserve(path,folder),'focal_rows':focal})
 candidates=old['candidates'];pit=[]
 for c in candidates:
  p=R/c['backup'];assert sha(p)==c['source_sha256']
  with p.open(encoding='utf-8-sig',newline='') as f:raw=[r for r in csv.reader(f) if r[0].removesuffix('.java')==j['focal_class'] and r[1].rsplit('.',1)[0]==ctx['package']]
  pit.append({'backup':c['backup'],'sha256':sha(p),'focal_mutants':len(raw),'status_counts':dict(Counter(r[5] for r in raw)),'archived_percent_matches':c['archived_percent_matches']})
 suite=bool(xmls) and all(x['all_cases_selected'] and x['errors']==0 and x['skipped']==0 for x in xmls)
 chain=suite and bool(jacoco) and len(pit)==1 and pit[0]['archived_percent_matches'] and logproof.get('one_measurement_after_GPT_start') and logproof.get('selected_G0_test_mentioned') and logproof.get('E0_scaffolding_move_failed')
 rows.append({'sample_index_1based':index,'class_key':j['class_key'],'original_G0_value_unchanged':old['frozen_G0_mutation_percent'],'archived_native_G0_suite_pass':suite,'PIT':pit,'suite_XML':xmls,'JaCoCo':jacoco,'execution_log':logproof,'ownership_conclusion':'SUPPORTED_BY_ARCHIVED_EXECUTION_CHAIN' if chain else 'UNRESOLVED_REQUIRES_REVIEW','limit':'Provenance from preserved per-class workspace/log/suite/report chain; CSV alone has no engine version or cryptographic execution timestamp. No G0 remeasurement.'})
result={'status':'READ_ONLY_PROVENANCE_AUDIT','rows':rows,'supported_count':sum(r['ownership_conclusion']=='SUPPORTED_BY_ARCHIVED_EXECUTION_CHAIN' for r in rows),'G0_values_changed':False,'G0_cohorts_changed':False,'new_measurements':0,'new_GPT_API_calls':0,'new_EvoSuite_calls':0}
dump(out/'result.json',result)
lines=['# Provenance của bốn điểm GPT Gradle bằng0','', 'Chỉ đọc log, suite XML, JaCoCo và PIT đã lưu; không chạy lại test hoặc tính lại bảng paper.','', '|Index|G0 giữ nguyên|Suite G0 pass|PIT focal/status|Kết luận provenance|','|---|---:|---|---|---|']
for r in rows:lines.append(f"|{r['sample_index_1based']}|{r['original_G0_value_unchanged']}|{r['archived_native_G0_suite_pass']}|{'; '.join(str(p['status_counts']) for p in r['PIT'])}|{r['ownership_conclusion']}|")
lines+=['','Chain được chấp nhận khi log chỉ có một measurement Gradle sau khi bắt đầu GPT, nhắc đúng testG0, EvoSuite cũ lỗi scaffold trước measurement; suiteXML đúng testG0 pass, có JaCoCo focal và một PIT CSV khớp điểm đã khóa. Đây là provenance của archived workspace, không phải tái thực nghiệm hoặc bằng chứng engine version từCSV.','', 'NO_COVERAGE cho biết mutant chưa được test bao phủ trong report đó; không tự diễn giải thành thiếu assertion, lỗi provider hoặc năng lực GPT nói chung. Thiết lập engine/mutators và miền mutant E1 vẫn phải được kiểm trước benchmark Gradle. Giữ nguyên G0, các mẫu RQ1–RQ3 và nămRQ.']
with (out/'REPORT.md').open('x',encoding='utf-8') as f:f.write('\n'.join(lines)+'\n')
audit.verify();audit.log('B1_GRADLE_G0_ZERO_PROVENANCE_AUDITED',result_sha256=sha(out/'result.json'),report_sha256=sha(out/'REPORT.md'),supported=result['supported_count'],new_measurements=0,GPT_API_calls=0);print(json.dumps({'status':result['status'],'supported':result['supported_count'],'reviewed':len(rows),'new_measurements':0,'GPT_API_calls':0},indent=2))
