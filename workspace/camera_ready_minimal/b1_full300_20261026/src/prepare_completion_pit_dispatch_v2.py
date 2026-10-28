"""Repair pre-spawn UI path only. Never change frozen v1 or experimental recipe."""
import ast,difflib,json
from maven_adapter_v1 import R,sha,dump
from parallel_pin_verify_v1 import verify_pins
A=R/'completion_amendment_v1'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
 oldout=R/'jobs/004_completion_pit_v1'
 assert not list((oldout/'commands').glob('*/started.json')),'Prior process ran; transport-only recovery inapplicable'
 old=R/'src/complete_gradle_pit_group_v1.py';new=R/'src/complete_gradle_pit_group_v2.py'
 text=old.read_text().replace("A/'progress.json'","R/'runtime/completion_progress.json'").replace('admission_gradle_pit_v1.json','admission_gradle_pit_v2.json').replace('gradle_pit_run_v1','gradle_pit_run_v2').replace('_completion_pit_v1','_completion_pit_v2')
 ast.parse(text)
 with new.open('x',encoding='utf-8') as f:f.write(text)
 out=A/'dispatcher_v2_preparation';out.mkdir()
 (out/'change.diff').write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
 dump(out/'receipt.json',{'reason':'UI target rejected before any command spawn','prior_job':str(oldout),'prior_started_commands':0,'experimental_recipe_changed':False,'new_runner_sha256':sha(new),'old_runner_sha256':sha(old),'score_based_retry':False,'post_outcome_technical_diagnostic':True})
 lock=load(A/'admission_gradle_pit_v1.json');lock['code_and_input_hashes'].update({str(p.resolve()):sha(p) for p in [new,R/'src/prepare_completion_pit_dispatch_v2.py',out/'receipt.json']})
 lock['dispatcher_prelaunch_correction']=str(out/'receipt.json');verify_pins(lock['code_and_input_hashes']);dump(A/'admission_gradle_pit_v2.json',lock)
 print('Sealed v2 pre-spawn UI path correction; experimental policy unchanged')
if __name__=='__main__':main()
