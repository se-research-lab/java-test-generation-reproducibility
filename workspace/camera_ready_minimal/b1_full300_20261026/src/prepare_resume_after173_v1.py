"""Write a resume command only. Does not release STOP or start a worker."""
import ast,difflib,json
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump
from parallel_pin_verify_v1 import verify_pins
A=R/'completion_amendment_v1';O=A/'pause_20261027_after173_v1'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
 checkpoint=load(O/'checkpoint.json');assert checkpoint['status']=='PAUSED_AFTER_CURRENT_CLASS_CHECKPOINT_VERIFIED' and checkpoint['remaining_indices']==[211,220,269,275,294]
 old=R/'src/complete_maven_groups_v4.py';new=R/'src/run_remaining5_after173_v1.py';text=old.read_text()
 replacements={"choices=['pom','junit3']":"choices=['pom']","admission=A/f'admission_maven_{group}_v3.json'":"admission=A/'pause_20261027_after173_v1/resume_admission_v1.json'","run=A/f'maven_{group}_run_v3'":"run=A/'maven_pom_resume_after173_v1'","f'{i:03d}_completion_{group}_v3'":"f'{i:03d}_completion_{group}_resume_after173_v1'"}
 for before,after in replacements.items():assert text.count(before)==1,(before,text.count(before));text=text.replace(before,after)
 ast.parse(text)
 with new.open('x',encoding='utf-8') as f:f.write(text)
 diff=O/'resume_dispatch_only.diff';diff.write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
 parent=A/'admission_maven_pom_v3.json';lock=load(parent);resume=json.loads(json.dumps(lock));resume['admitted_sample_indices']=checkpoint['remaining_indices'];resume['generation_allowed_indices']=checkpoint['remaining_indices'];resume['scope']='user-requested resume of five uncompleted classes after verified173; experimental policy unchanged';resume['parent_admission_sha256']=sha(parent);resume['resume_checkpoint_sha256']=sha(O/'checkpoint.json');resume['prepared_utc']=datetime.now(timezone.utc).isoformat()
 resume['code_and_input_hashes'].update({str(p.resolve()):sha(p) for p in [new,R/'src/resume_user_paused_e1_v1.py',O/'checkpoint.json',O/'checkpoint_pins.json',O/'accepted25.json',O/'remaining5.json',O/'current173_complete_archive.json',diff]})
 changed={k for k in set(lock)|set(resume) if lock.get(k)!=resume.get(k)}
 allowed={'admitted_sample_indices','generation_allowed_indices','scope','parent_admission_sha256','resume_checkpoint_sha256','prepared_utc','code_and_input_hashes'};assert changed<=allowed
 assert all(resume['code_and_input_hashes'][k]==v for k,v in lock['code_and_input_hashes'].items())
 verify_pins(resume['code_and_input_hashes']);verify_pins(resume['tool_hashes']);dump(O/'resume_admission_v1.json',resume)
 dump(O/'resume_preparation.json',{'prepared_only_not_started':True,'parent_admission_sha256':sha(parent),'resume_admission_sha256':sha(O/'resume_admission_v1.json'),'control_fields_changed':sorted(changed),'experimental_core_hashes_preserved':True,'profile_seed_budget_target_mutators_dependencies_changed':False,'must_not_rerun_indices':checkpoint['accepted25_indices'],'resume_only_indices':checkpoint['remaining_indices'],'STOP_still_present':(R/'STOP_REQUESTED.json').exists(),'new_experiment_calls':0})
 print('Resume command prepared only; STOP remains; no worker launched')
if __name__=='__main__':main()
