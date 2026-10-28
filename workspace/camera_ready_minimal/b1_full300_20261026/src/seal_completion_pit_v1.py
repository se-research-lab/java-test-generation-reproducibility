import ast,json,sys
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump
from parallel_pin_verify_v1 import verify_pins
A=R/'completion_amendment_v1'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
 fixture=R/'validation/gradle_tool_repository_amendment_fixture_v1/gradle_2.13/result.json'
 assert load(fixture)['status']=='PASS_SYNTHETIC_NATIVE_MEASUREMENT_ONLY'
 census=load(A/'input_audit/class_census300.json');indices=[x['index'] for x in census if 'PIT_TOOL_RESOLUTION' in x['groups']]
 assert indices==[x['index'] for x in census if x['repo_id']=='41627638']
 lock=load(R/'admission_gradle_full40_v1.json');pins=lock['code_and_input_hashes'].copy()
 for p in [R/'src/complete_gradle_pit_group_v1.py',R/'src/gradle_tool_repository_amendment_v1.py',R/'src/seal_completion_pit_v1.py',A/'POLICY.md',A/'input_audit/class_census300.json',fixture]:
  if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8'))
  pins[str(p.resolve())]=sha(p)
 for i in indices:
  old=R/'jobs'/f'{i:03d}_gradle_v1'
  for row in load(old/'artifact_manifest.json'):pins[str((old/row['relative']).resolve())]=row['sha256']
 verify_pins(pins)
 lock.update(admitted_sample_indices=indices,code_and_input_hashes=pins,post_outcome_amendment=True,admitted_utc=datetime.now(timezone.utc).isoformat(),new_generation_authorized=False,maximum_measurement_attempts_per_class=1,selection='single amendment attempt independent of score',parent_admission_sha256=sha(R/'admission_gradle_full40_v1.json'),policy_sha256=sha(A/'POLICY.md'),fixture_sha256=sha(fixture))
 dump(A/'admission_gradle_pit_v1.json',lock)
 print('SEALED measurement-only PIT group',indices,sha(A/'admission_gradle_pit_v1.json'))
if __name__=='__main__':main()
