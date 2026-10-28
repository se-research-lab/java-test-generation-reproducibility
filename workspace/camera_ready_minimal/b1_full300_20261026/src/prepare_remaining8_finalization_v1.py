"""Prepare offline audit/history/package for the last untouched POM classes."""
import ast,difflib
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1'
def main():
 out=A/'remaining8_finalization_preparation_v1';out.mkdir(exist_ok=False);variants=[]
 old=R/'src/audit_completion_results_v4.py';t=old.read_text()
 t=t.replace('d=load(path);folder=path.parent','d=load(path);folder=Path(d.get(\'raw_job_path\',str(path.parent)))')
 t=t.replace("assert path.relative_to(folder).as_posix() in entries,'Selected result not sealed'","""if path.parent.resolve()!=folder.resolve():
  expected=A/'result_reconciliations_v1/112/result.json'
  assert j['sample_index_1based']==112 and path.resolve()==expected.resolve(),'Unrecognized external result'
  receipt=load(expected.parent/'reconciliation.json')
  assert sha(path)==receipt['result_sha256'] and sha(manifest)==receipt['original_archive_sha256'],'Reconciled112 anchor drift'
  assert receipt['original_job_modified'] is False and receipt['new_generation_calls']==receipt['new_measurement_calls']==0
 else:assert path.relative_to(folder).as_posix() in entries,'Selected result not sealed'""")
 t=t.replace("('pom','v2'),('junit3','v2')","('pom','v2'),('pom','v3'),('junit3','v2')")
 needle='  # Preserve the pre-spawn dispatcher failure as an attempt with zero starts.'
 addition="""  if i==112 and (A/'result_reconciliations_v1/112/result.json').exists():
   selected=A/'result_reconciliations_v1/112/result.json';amendment='pom'
   attempts.append({'index':i,'class_key':j['class_key'],'phase':'read_only_timeout112_reconciliation','folder':str(R/'jobs/112_completion_pom_v2'),'commands':[],'result':pin(selected),'selection':'same completed300s timeout; no generation or measurement rerun','new_generation_allowed':False})
"""
 assert needle in t;t=t.replace(needle,addition+needle)
 t=t.replace("'generation':'COMPLETE_SUITE'", "'generation':'COMPLETE_SUITE'")
 variants.append((old,R/'src/audit_completion_results_v5.py',t))
 old=R/'src/export_completion_history_v1.py';t=old.read_text().replace("analysis=A/'analysis_v1'","analysis=A/'analysis_v2'").replace("out=A/'history_delivery_v1'","out=A/'history_delivery_v2'").replace("'pom_v2','junit3_v1'","'pom_v2','pom_v3','junit3_v1'")
 variants.append((old,R/'src/export_completion_history_v2.py',t))
 old=R/'src/package_completion_evidence_v2.py';t=old.read_text().replace("analysis=A/'analysis_v1'","analysis=A/'analysis_v2'").replace("out=A/'delivery_v1'","out=A/'delivery_v2'").replace("'history_delivery_v1']:","'history_delivery_v2','result_reconciliations_v1','partial_pit_preparation_v1','remaining_pom8_launch_v1','maven_pom_run_v3','remaining8_finalization_preparation_v1']:").replace('E1_completion_private_evidence_v1.zip','E1_completion_private_evidence_v2.zip')
 variants.append((old,R/'src/package_completion_evidence_v3.py',t))
 old=R/'src/finalize_completion_when_ready_v2.py';t=old.read_text().replace("O=A/'automatic_finalization_v2'","O=A/'automatic_finalization_v3'").replace("A/'stage_sequence_v1/complete.json'","A/'remaining_pom8_launch_v1/complete.json'").replace('audit_completion_results_v4.py','audit_completion_results_v5.py').replace("['--output','analysis_v1']","['--output','analysis_v2']").replace('export_completion_history_v1.py','export_completion_history_v2.py').replace('package_completion_evidence_v2.py','package_completion_evidence_v3.py').replace("'completion_final_'+label+'_v1'","'completion_remaining8_final_'+label+'_v2'").replace("A/'analysis_v1/statistics.json'","A/'analysis_v2/statistics.json'")
 variants.append((old,R/'src/finalize_completion_when_ready_v3.py',t))
 for old,new,text in variants:
  ast.parse(text)
  with new.open('x',encoding='utf-8') as f:f.write(text)
  (out/(new.stem+'.diff')).write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
 dump(out/'receipt.json',{'scope':'offline finalization after remaining8; add explicit read-only112 reconciliation and allattempts','new_experiment_calls':0,'new_analysis_namespace':'analysis_v2','new_history_namespace':'history_delivery_v2','new_package_namespace':'delivery_v2','old_outputs_retained':True})
 print('Prepared finalization v3; older partial snapshots retained')
if __name__=='__main__':main()
