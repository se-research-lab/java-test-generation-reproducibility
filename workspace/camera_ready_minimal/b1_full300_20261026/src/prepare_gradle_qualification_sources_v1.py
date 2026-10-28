"""Create v2 guard copies and static validator; no tool/runtime execution."""
import ast,sys
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
mapping=[('gradle_command_policy_v1.py','gradle_command_policy_v2.py'),('gradle_process_supervisor_v1.py','gradle_process_supervisor_v2.py'),('validate_gradle_command_policy_v1.py','validate_gradle_command_policy_v2.py')]
records=[]
for old,new in mapping:
 source=R/'src'/old;target=R/'src'/new;text=source.read_text(encoding='utf-8')
 text=text.replace("PRIVATE_HOME=R/'cache_preparation_gradle_v1/home'","PRIVATE_HOME=R/'cache_preparation_gradle_v1/gradle_user_home'")
 text=text.replace('gradle_command_policy_v1','gradle_command_policy_v2').replace('gradle_process_supervisor_v1','gradle_process_supervisor_v2').replace('B1_gradle_supervisor_v1','B1_gradle_supervisor_v2').replace('gradle_guard_prototype','gradle_guard_v2')
 if new=='gradle_command_policy_v2.py':
  text=text.replace("ensure(qualification,'Version/help are qualification-only')","ensure(qualification,'Version/help are qualification-only')\n    if stage=='version':ensure(self.lock.get('init_script') is None,'Version qualification forbids init scripts')")
 if new=='validate_gradle_command_policy_v2.py':
  text=text.replace("for stage in ['compile_classpath','test_jacoco','pit']:","assert policy.validate(head+['--version'],root,30,'version')[0]==head+['--version']\n for stage in ['compile_classpath','test_jacoco','pit']:")
  text=text.replace("checks.append('owned pinned init script accepted')","checks.append('owned pinned init script accepted for task plans')\nreject('version qualification forbids even owned init script',lambda:p.validate(head+['--init-script',str(init.resolve()),'--version'],root,30,'version'))")
  text=text.replace('No copied distribution/dependency cache qualification','Private cache preparation is separate; this static validator does not qualify runtime')
 ast.parse(text)
 with target.open('x',encoding='utf-8') as f:f.write(text)
 records.append({'source':str(source),'source_sha256':sha(source),'new_file':str(target),'new_sha256':sha(target)})
runner=R/'src/run_gradle_versions_qualification_v1.py';ast.parse(runner.read_text(encoding='utf-8'))
record={'scope':'source copies/static syntax only; no Java/Gradle/runtime execution','files':records,'runner_prepared_not_executed':{'path':str(runner),'sha256':sha(runner)},'new_experiment_calls':0}
dump(R/'audit/gradle_qualification_sources_v2.json',record)
audit.log('B1_GRADLE_QUALIFICATION_SOURCES_V2_CREATED',registry_sha256=sha(R/'audit/gradle_qualification_sources_v2.json'),new_experiment_calls=0)
print('v2 policy/supervisor/validator prepared; v1 preserved; no runtime admission')
