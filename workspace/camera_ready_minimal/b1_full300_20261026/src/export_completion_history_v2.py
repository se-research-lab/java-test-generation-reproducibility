"""Readable all-class history plus stage evidence, independent of benchmark execution."""
import json,csv,re,shutil,sys
from collections import Counter
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
 analysis=A/'analysis_v2';rows=load(analysis/'class_results300.json');out=A/'history_delivery_v2';out.mkdir(exist_ok=False)
 old=load(R/'policy_attempt_history_v2/selection_current.json');records=[];summaries=[]
 for r,h in zip(rows,old):
  i=r['index'];folders=[]
  original=R/'jobs'/f'{i:03d}_gradle_v1'
  if original.exists():folders.append(('original_gradle_frozen_v1',original))
  for suffix in ['pit_v1','pit_v2','pom_v1','pom_v2','pom_v3','junit3_v1','junit3_v2']:
   p=R/'jobs'/f'{i:03d}_completion_{suffix}'
   if p.exists():folders.append(('completion_'+suffix,p))
  actual_gen=0;new_suites=[];phases=[]
  for phase,folder in folders:
   phase_rows=[]
   for plan in sorted((folder/'commands').glob('*/plan.json')):
    d=load(plan);argv=d['argv'];f=plan.parent/'finished.json';end=load(f) if f.exists() else {};started=(plan.parent/'started.json').is_file()
    gen='-jar' in argv;kind='GENERATION' if gen else 'PIT_MEASUREMENT' if any('mutationCoverage' in x or x.endswith('pitest') for x in argv) else 'TEST_EXECUTION' if any(x.endswith('b1NativeTest') for x in argv) or 'test' in argv else 'COMPILE_OR_AUDIT'
    actual_gen+=int(gen and started)
    seed=argv[argv.index('-seed')+1] if '-seed' in argv else None
    row={'index':i,'class_key':r['class_key'],'phase':phase,'command_index':plan.parent.name,'kind':kind,'started':started,'returncode':end.get('returncode'),'timeout':end.get('reason')=='TIMEOUT','seed':seed,'argv':argv,'plan_path':str(plan),'plan_sha256':sha(plan),'finished_path':str(f) if f.exists() else None,'suite_edited_by_policy':False,'scope':'post-outcome amendment' if 'completion' in phase else 'original frozen Gradle policy'}
    records.append(row);phase_rows.append(row)
   changes=[]
   for p in folder.glob('*.diff'):changes.append({'path':str(p),'sha256':sha(p)})
   suite=folder/'native_generated.json'
   if suite.exists():new_suites.append({'phase':phase,'source':str(suite),'sha256':sha(suite),'complete':load(suite).get('complete')})
   phases.append({'phase':phase,'folder':str(folder),'started_commands':sum(x['started'] for x in phase_rows),'actual_generation_calls':sum(x['kind']=='GENERATION' and x['started'] for x in phase_rows),'changes':changes,'result':str(folder/'result.json') if (folder/'result.json').exists() else None,'unresolved':load(folder/'unresolved.json') if (folder/'unresolved.json').exists() else None})
  summary={'index':i,'class_key':r['class_key'],'historical_Maven_E49_history':h,'new_or_Gradle_phases':phases,'actual_generation_calls_in_addendum':actual_gen,'new_suite_receipts':new_suites,'selected_result':r['selected_result'],'selection_rule':'old selected record retained unless originally unscored; eligible single new attempt, independent of score; test-only stages do not supply PIT or historical process gate','observed_mutation_percent':r['observed_mutation_percent'],'end_to_end_score_percent':r['end_to_end_score_percent'],'score_basis':r['score_basis'],'unresolved':r['unresolved']};summaries.append(summary)
  if 'JUNIT3_SUPPORT' in r['review_groups']:assert not any(x['index']==i and 'completion' in x['phase'] and x['kind']=='GENERATION' and x['started'] for x in records)
  if 'PIT_TOOL_RESOLUTION' in r['review_groups']:assert not any(x['index']==i and 'completion' in x['phase'] and x['kind']=='GENERATION' and x['started'] for x in records)
 assert len(summaries)==300
 dump(out/'class_policy_attempt_history300.json',summaries);dump(out/'command_attempts_addendum.json',records)
 lines=['# Lịch sử policy và attempts — 300 class','', 'Đây là bản ghép lịch sử cũ với Gradle và các bổ sung sau quan sát lỗi. Các file cũ không bị ghi đè. Điều kiện retry kỹ thuật đã định trong E1 khác với readmission sau chẩn đoán adapter/input; cả hai được ghi rõ trong policy và receipts. Không chọn điểm lớn nhất.','', '| Index | Class key | Các phase bổ sung | Gen thực chạy trong addendum | Điểm PIT quan sát | Strict có cơ sở | Trạng thái |','|---:|---|---|---:|---:|---:|---|']
 for r in summaries:
  phases='; '.join(x['phase']+f" ({x['started_commands']} commands)" for x in r['new_or_Gradle_phases']) or 'xem lịch sử Maven/E49 gốc'
  lines.append(f"| {r['index']} | {r['class_key']} | {phases} | {r['actual_generation_calls_in_addendum']} | {r['observed_mutation_percent']} | {r['end_to_end_score_percent']} | {'unresolved' if r['unresolved'] else r['score_basis']} |")
 (out/'CLASS_HISTORY300.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 dump(out/'verification.json',{'n':300,'unique_class_keys':len({x['class_key'] for x in summaries}),'JUnit3_new_generation':0,'PIT_resolution_new_generation':0,'new_calls_by_phase':dict(Counter(x['phase'] for x in records if x['kind']=='GENERATION' and x['started'])),'old_history_sha256':sha(R/'policy_attempt_history_v2/selection_current.json'),'no_max_score_selection':True})
 dump(out/'MANIFEST.json',[{'path':p.name,'sha256':sha(p)} for p in out.iterdir() if p.is_file()]);print('History delivered for 300 unique classes')
if __name__=='__main__':main()
