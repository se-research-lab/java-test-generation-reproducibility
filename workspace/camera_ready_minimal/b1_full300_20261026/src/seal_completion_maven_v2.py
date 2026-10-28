import argparse,ast,json
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump
from parallel_pin_verify_v1 import verify_pins
A=R/'completion_amendment_v1'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
 p=argparse.ArgumentParser();p.add_argument('--group',choices=['pom','junit3'],required=True);group=p.parse_args().group
 fixture=R/'validation'/('completion_maven_'+group+'_v2')/'result.json';assert load(fixture)['status']=='PASS_SYNTHETIC_ONLY'
 lock=load(R/'admission_maven_v6.json');census=load(A/'input_audit/class_census300.json');name='POM_INPUT' if group=='pom' else 'JUNIT3_SUPPORT';indices=[r['index'] for r in census if name in r['groups']];assert len(indices)==10
 pins=lock['code_and_input_hashes'].copy()
 code=['complete_maven_groups_v1.py','pom_completion_controller_v1.py','pom_namespace_completion_v1.py','completion_measurement_commands_v1.py','junit3_test_support_completion_v1.py','seal_completion_maven_v2.py']
 for p in [R/'src'/n for n in code]+[A/'POLICY.md',A/'MAVEN_POLICY_ANNEX.md',A/'input_audit/class_census300.json',fixture]:
  if p.suffix=='.py':ast.parse(p.read_text(encoding='utf-8'))
  pins[str(p.resolve())]=sha(p)
 for i in indices:
  if group=='pom':
   for p in (A/'input_audit/pom_provenance'/f'{i:03d}').glob('*'):pins[str(p.resolve())]=sha(p)
  else:
   old=R/'jobs'/f'{i:03d}'
   for row in load(old/'artifact_manifest.json'):pins[str((old/row['relative']).resolve())]=row['sha256']
 verify_pins(pins)
 lock.update(scope='post_outcome_Maven_'+group,admitted_sample_indices=indices,code_and_input_hashes=pins,post_outcome_amendment=True,admitted_utc=datetime.now(timezone.utc).isoformat(),generation_allowed=group=='pom',maximum_measurement_attempts_per_class=1,selection_rule='single sealed amended attempt, no best-of',parent_admission_sha256=sha(R/'admission_maven_v6.json'),policy_sha256=sha(A/'POLICY.md'),annex_sha256=sha(A/'MAVEN_POLICY_ANNEX.md'))
 dump(A/f'admission_maven_{group}_v1.json',lock);print('SEALED',group,indices,flush=True)
if __name__=='__main__':main()
