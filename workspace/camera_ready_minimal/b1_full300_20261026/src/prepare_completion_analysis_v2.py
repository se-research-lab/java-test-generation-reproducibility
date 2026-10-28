"""Offline analyzer version: stage-qualified JUnit3 has no historical PIT process gate."""
import ast,difflib
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1'
def main():
 old=R/'src/audit_completion_results_v1.py';new=R/'src/audit_completion_results_v2.py';text=old.read_text()
 text=text.replace("[('pit','v2'),('pom','v1'),('junit3','v1')]","[('pit','v2'),('pom','v1'),('pom','v2'),('junit3','v2')]")
 before="if selected and selected.exists():\n   ev=evidence(j,selected);raw=ev.pop('raw');cmd=ev.pop('commands');row.update(ev);row['selected_legacy_strict']=raw['legacy_strict_mutation_percent'];row['end_to_end_score_percent']=None;row['score_basis']='UNRESOLVED'"
 after=before+"\n   if raw.get('test_only_process_gate') is not None:\n    row['test_only_process_gate']=raw['test_only_process_gate'];row['process_gate']=None;row['selected_legacy_strict']=None;row['PIT']='UNRESOLVED_PROVIDER_NOT_QUALIFIED'"
 assert before in text;text=text.replace(before,after)
 text=text.replace("stats={'n':300,","stats={'n':300,'new_PIT_group_completed':sum(r['new_amendment_group']=='pit' for r in rows),'new_Maven_POM_results':sum(r['new_amendment_group']=='pom' for r in rows),'new_JUnit3_test_only_results':sum(r['new_amendment_group']=='junit3' for r in rows),")
 text=text.replace("if row['PIT']=='ZERO_FOCAL_MUTANTS':row['score_basis']='UNDEFINED_ZERO_FOCAL_MUTANTS_NO_PRIMARY_ZERO_FILL'","if row['PIT']=='ZERO_FOCAL_MUTANTS':row['score_basis']='UNDEFINED_ZERO_FOCAL_MUTANTS_NO_PRIMARY_ZERO_FILL'\n   if raw.get('test_only_process_gate') is not None:row['score_basis']='UNRESOLVED_PIT; TEST_ONLY_LIFECYCLE_REPORTED_SEPARATELY'")
 ast.parse(text)
 with new.open('x',encoding='utf-8') as f:f.write(text)
 out=A/'analysis_v2_preparation';out.mkdir();(out/'change.diff').write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
 dump(out/'receipt.json',{'old_sha256':sha(old),'new_sha256':sha(new),'purpose':'recognize new result namespaces and avoid interpreting test-only gate as historical verify+PIT gate','new_experiment_calls':0})
 print('Prepared offline analyzer v2')
if __name__=='__main__':main()
