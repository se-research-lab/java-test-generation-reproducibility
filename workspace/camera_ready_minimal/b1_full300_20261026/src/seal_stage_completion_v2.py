import argparse,json,ast
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump
from parallel_pin_verify_v1 import verify_pins
A=R/'completion_amendment_v1'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
 p=argparse.ArgumentParser();p.add_argument('--group',choices=['pom','junit3'],required=True);group=p.parse_args().group
 fixture=R/'validation/completion_maven_pom_v3/result.json' if group=='pom' else R/'validation/completion_maven_junit3_v3/evidence.json'
 if group=='pom':assert load(fixture)['status']=='PASS_SYNTHETIC_ONLY'
 else:
  ev=load(fixture);assert ev['strict_suite_evidence'] and not ev['pit_report_present'];assert (fixture.parent/'failure.json').exists()
  assert load(fixture.parent/'before_dependency.json')['compile_classpath']==load(fixture.parent/'after_dependency.json')['compile_classpath']
 lock=load(R/'admission_maven_v6.json');pins=lock['code_and_input_hashes'].copy();census=load(A/'input_audit/class_census300.json');indices=[x['index'] for x in census if ('POM_INPUT' if group=='pom' else 'JUNIT3_SUPPORT') in x['groups']]
 codes=['complete_maven_groups_v3.py','completion_measurement_commands_v3.py','flatten_output_guard_completion_v1.py','pom_completion_controller_v2.py','pom_namespace_completion_v1.py','junit3_test_support_completion_v1.py','seal_stage_completion_v2.py']
 for p in [R/'src'/n for n in codes]+[A/'POLICY.md',A/'MAVEN_POLICY_ANNEX.md',A/'STAGE_POLICY_ANNEX_V2.md',A/'stage_completion_v4_preparation/receipt.json',A/'stage_completion_v4_preparation/072_generation_bytecode_baseline.json',fixture]:
  if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8'))
  pins[str(p.resolve())]=sha(p)
 for i in indices:
  if group=='pom' and i!=72:
   for p in (A/'input_audit/pom_provenance'/f'{i:03d}').glob('*'):pins[str(p.resolve())]=sha(p)
  else:
   old=R/'jobs'/('072_completion_pom_v1' if i==72 else f'{i:03d}')
   for row in load(old/'artifact_manifest.json'):pins[str((old/row['relative']).resolve())]=row['sha256']
 verify_pins(pins)
 lock.update(scope='post_diagnostic_stage_completion_'+group,admitted_sample_indices=indices,code_and_input_hashes=pins,post_outcome_amendment=True,admitted_utc=datetime.now(timezone.utc).isoformat(),generation_allowed=group=='pom',generation_prohibited_indices=indices if group=='junit3' else [72],generation_allowed_indices=[] if group=='junit3' else [i for i in indices if i!=72],PIT_execution_allowed=group=='pom',maximum_stage_attempts_per_class=1,selection_rule='single sealed stage continuation; no best-of',annex_sha256=sha(A/'STAGE_POLICY_ANNEX_V2.md'))
 dump(A/f'admission_maven_{group}_v2.json',lock);print('SEALED STAGE',group,indices,flush=True)
if __name__=='__main__':main()
