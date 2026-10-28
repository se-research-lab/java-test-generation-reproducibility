"""Add initial Gradle attempts and non-score-based original-index3 sensitivity."""
import ast,difflib
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1'
def main():
 old=R/'src/audit_completion_results_v2.py';new=R/'src/audit_completion_results_v3.py';text=old.read_text()
 before="amendment=None\n  for group,version"
 after="""amendment=None
  original_gradle=R/'jobs'/f'{i:03d}_gradle_v1'
  if original_gradle.exists():attempts.append({'index':i,'class_key':j['class_key'],'phase':'original_gradle_frozen_v1','folder':str(original_gradle),'commands':commands(original_gradle),'result':pin(original_gradle/'result.json') if (original_gradle/'result.json').exists() else None,'selection':'original frozen one-pass policy; not overwritten'})
  for group,version"""
 assert before in text;text=text.replace(before,after)
 before="stats['fixed49_unchanged']="
 addition="""initial3=load(R/'jobs/003/result.json')['legacy_strict_mutation_percent']
 stats['original_index3_sensitivity']={'initial_result_sha256':sha(R/'jobs/003/result.json'),'E1_mean_available':cluster([(r['repo_id'],initial3 if r['index']==3 else r['end_to_end_score_percent']) for r in known]),'G0_minus_E1_available':cluster([(r['repo_id'],r['G0_strict']-(initial3 if r['index']==3 else r['end_to_end_score_percent'])) for r in known]),'note':'restore original class3 outcome, no best-of'}
 stats['fixed49_unchanged']="""
 assert before in text;text=text.replace(before,addition)
 ast.parse(text)
 with new.open('x',encoding='utf-8') as f:f.write(text)
 out=A/'analysis_v3_preparation';out.mkdir();(out/'change.diff').write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8');dump(out/'receipt.json',{'old_sha256':sha(old),'new_sha256':sha(new),'scope':'offline history and sensitivity only','new_experiment_calls':0})
 print('Prepared offline audit v3')
if __name__=='__main__':main()
