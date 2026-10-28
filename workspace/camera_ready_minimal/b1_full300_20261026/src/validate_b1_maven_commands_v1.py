"""Pure command admission checks: no subprocess invocation or batch admission."""
import json,subprocess
from pathlib import Path
from b1_maven_commands_v1 import MavenCommands
from maven_adapter_v1 import R,GuardAbort,generation_bindings,sha,dump
O=R/'validation/b1_maven_commands_v1';O.mkdir(parents=True,exist_ok=False);(O/'repo/module').mkdir(parents=True)
class NoCommands:
 TimeoutExpired=subprocess.TimeoutExpired
 def run(self,*args,**kwargs):raise GuardAbort('No processes in contract fixture')
obj=MavenCommands.__new__(MavenCommands);obj.out=O.resolve();obj.cache=(R/'cache_preparation_v1/maven_cache').resolve();obj.job={'module':'module','selected_test_fqcn':'fixture.A_ESTest'}
obj.skip=generation_bindings(NoCommands(),O,lambda *args,**kw:None)['common_maven_skip_args']()
module=O/'repo/module';base=['mvn','-Dtest=fixture.A_ESTest',*obj.skip]
measure=[*base,'clean','verify','jacoco:prepare-agent','jacoco:report','org.pitest:pitest-maven:mutationCoverage']
actual=obj.maven_args(measure,module,300);assert '-o' in actual and '-Dmaven.repo.local='+str(obj.cache) in actual
checks=['measurement_exact_full_lifecycle_private_cache']
compile=['mvn',*obj.skip,'-DskipTests=true','compile','dependency:build-classpath','-Dmdep.outputFile='+str(module/'target/evosuite-classpath.txt')]
obj.maven_args(compile,module,300);checks.append('generation_compile_exact_flags')
obj.maven_args([*base,'org.apache.maven.plugins:maven-help-plugin:3.2.0:effective-pom','-Doutput='+str(O/'effective.xml')],module,180);checks.append('effective_POM_bounded_output')
for name,args,cwd,timeout in [('missing_skip',measure[:-1],module,300),('different_timeout',measure,module,900),('changed_test',[x.replace('fixture.A_ESTest','fixture.B_ESTest') for x in measure],module,300),('external_workdir',measure,R,300),('external_output',[*base,'org.apache.maven.plugins:maven-help-plugin:3.2.0:effective-pom','-Doutput='+str(R/'overwrite.xml')],module,180),('extra_goal',[*base,'deploy'],module,180),('online_property',measure+['-o=false'],module,300)]:
 try:obj.maven_args(args,cwd,timeout)
 except GuardAbort:checks.append(name)
 else:raise AssertionError(name)
report={'status':'PASS','checks':checks,'count':len(checks),'bridge_sha256':sha(R/'src/b1_maven_commands_v1.py'),'experiment_calls':0,'benchmark_admitted':False,'limitation':'pure command grammar; real controller integration still pending'}
dump(O/'result.json',report);print(json.dumps(report,indent=2))
