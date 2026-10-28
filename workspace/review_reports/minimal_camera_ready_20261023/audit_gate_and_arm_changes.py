"""Read-only audit: historical vs V6 gates, build tools and GPT output bytes."""
from pathlib import Path
import json, hashlib, re
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent
w=pd.read_csv(ROOT/'scripts_v2/results/runs/full300_merged_20260724_paper/metrics_wide.csv').set_index('class_key')
a=pd.read_csv(ROOT/'review_reports/v6_final_20261021/data/attempts_1080.csv')
a=a[a.replicate.eq(0)].copy()
av=pd.read_csv(ROOT/'review_reports/reuse_audit_v1_20261021T112500/evidence/G0_AVAILABILITY_300.csv').set_index('class_key')
assert len(a)==600 and not a.duplicated(['class_key','arm']).any()
out={'scope':'read-only; no generation/measurement', 'groups':{},'gate_switch_records':[]}
for arm,oldarm in [('GPT','gpt'),('E1','evosuite')]:
 z=a[a.arm.eq(arm)].set_index('class_key').join(w[[f'{oldarm}_compilation',f'{oldarm}_strict_mutation_coverage']])
 for tool in ['all','maven','gradle']:
  sub=z if tool=='all' else z[z.build_tool.eq(tool)]
  old=sub[f'{oldarm}_compilation'].eq(1)
  entry={'n':len(sub),'old_build':int(old.sum()),'P_build':int(sub.P_success.sum()),'C_build':int(sub.C_process_success.sum()),'old_mean':float(sub[f'{oldarm}_strict_mutation_coverage'].mean()),'P_mean':float(sub.P_score_pct.mean()),'C_mean':float(sub.C_score_pct.mean())}
  for view,col in [('P','P_success'),('C','C_process_success')]:
   new=sub[col].eq(1)
   entry[view+'_transitions']={'old1_new1':int((old&new).sum()),'old1_new0':int((old&~new).sum()),'old0_new1':int((~old&new).sum()),'old0_new0':int((~old&~new).sum())}
  out['groups'][f'{arm}_{tool}']=entry
 for key,row in z[z.P_success.ne(z.C_process_success)].iterrows():
  raw=json.loads(Path(row.attempt_path).read_text(encoding='utf-8'))
  m=raw['measurement'];tests=m['tests'];commands=m['native_commands']
  log=Path(row.measurement_dir)/'native_verify_jacoco_pit.stdout.log'
  assert row.build_tool=='maven' and log.is_file() and 'BUILD SUCCESS' in log.read_text(encoding='utf-8',errors='replace')
  assert tests['failures']+tests['errors']>0
  assert not tests['valid_execution'] and not raw['buildable']
  out['gate_switch_records'].append({'class_key':key,'arm':arm,'failures':tests['failures'],'errors':tests['errors'],'total_mutants':m['mutation']['total_mutants'],'killed_mutants':m['mutation']['killed_mutants'],'C_score':float(row.C_score_pct),'attempt_path':row.attempt_path})
diff=[]
for row in a[a.arm.eq('GPT')].itertuples():
 p=av.loc[row.class_key,'G0_path']
 if pd.isna(p) or not Path(p).is_file():continue
 old=Path(p).read_bytes();new=Path(row.GPT_java).read_bytes()
 ot=old.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n');nt=new.decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n')
 diff.append({'class_key':row.class_key,'build_tool':row.build_tool,'bytes_differ':old!=new,'normalized_newlines_differ':ot!=nt,'whitespace_removed_differ':re.sub(r'\s+','',ot)!=re.sub(r'\s+','',nt)})
d=pd.DataFrame(diff)
out['gpt_outputs']={'n':len(d),'bytes_differ':int(d.bytes_differ.sum()),'normalized_newlines_differ':int(d.normalized_newlines_differ.sum()),'whitespace_removed_differ':int(d.whitespace_removed_differ.sum())}
out['gpt_outputs_by_tool']=d.groupby('build_tool').agg(n=('class_key','size'),semantic_text_difference_proxy=('whitespace_removed_differ','sum')).to_dict(orient='index')
out['note']='Whitespace removal is textual comparison only, not semantic equivalence. P/C is exact reclassification of same V6 records; old vs new is not causal isolation.'
d.to_csv(OUT/'gpt_old_new_output_comparison.csv',index=False,encoding='utf-8-sig')
pd.DataFrame(out['gate_switch_records']).to_csv(OUT/'pc_gate_switches_verified.csv',index=False,encoding='utf-8-sig')
(OUT/'gate_arm_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k!='gate_switch_records'},ensure_ascii=False,indent=2))
print('Raw gate switches verified:',len(out['gate_switch_records']))
