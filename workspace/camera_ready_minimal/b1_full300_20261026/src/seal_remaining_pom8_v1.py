import json,ast
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump
from parallel_pin_verify_v1 import verify_pins
A=R/'completion_amendment_v1'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
 lock=load(A/'admission_maven_pom_v2.json');indices=[119,163,173,211,220,269,275,294]
 assert load(A/'partial_pit_preparation_v1/qualification.json')['status']=='PASS_OFFLINE_PARSER_NO_EXECUTION'
 for i in indices:assert not (R/'jobs'/f'{i:03d}_completion_pom_v2').exists() and not (R/'jobs'/f'{i:03d}_completion_pom_v3').exists()
 pins=lock['code_and_input_hashes'].copy()
 for p in [R/'src'/n for n in ['measurement_parser_completion_v2.py','pom_completion_controller_v3.py','complete_maven_groups_v4.py','seal_remaining_pom8_v1.py']]+[A/'PARTIAL_PIT_POLICY_V3.md',A/'partial_pit_preparation_v1/qualification.json']:
  if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8'))
  pins[str(p.resolve())]=sha(p)
 verify_pins(pins);lock.update(admitted_sample_indices=indices,generation_allowed_indices=indices,generation_prohibited_indices=[72,112],code_and_input_hashes=pins,scope='post_diagnostic_parser_only_continuation_remaining_POM8',admitted_utc=datetime.now(timezone.utc).isoformat(),parent_admission_sha256=sha(A/'admission_maven_pom_v2.json'),parser_amendment_sha256=sha(A/'PARTIAL_PIT_POLICY_V3.md'),no_retry_112=True,maximum_stage_attempts_per_class=1)
 dump(A/'admission_maven_pom_v3.json',lock);print('SEALED remaining8; no rerun72/112; profile, seed, caps, PIT targets unchanged')
if __name__=='__main__':main()
