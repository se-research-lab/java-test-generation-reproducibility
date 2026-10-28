"""Seal stage-qualified test support and derived-POM handling; keep every prior attempt."""
import ast,difflib,json
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
 out=A/'stage_completion_v4_preparation';out.mkdir(exist_ok=False);variants=[]
 old=R/'src/completion_measurement_commands_v2.py';text=old.read_text()
 # Extend only test lifecycle grammar; use inherited offline/private-cache validation.
 text += '''
 def maven_args(self,args,cwd,timeout):
  module=(self.out/'repo'/self.job['module']).resolve()
  settings=['-s',str(self.out/'settings.xml')] if (self.out/'settings.xml').is_file() else []
  expected=[*settings,'-Dtest='+self.job['selected_test_fqcn'],*self.skip,'clean','test','jacoco:prepare-agent','jacoco:report']
  if args[1:]==expected:
   assert Path(cwd).resolve()==module and timeout==300,'Test-only stage boundary'
   return [str(MVN),'-o','-Dmaven.repo.local='+str(self.cache),*args[1:]]
  return super().maven_args(args,cwd,timeout)
'''
 variants.append((old,R/'src/completion_measurement_commands_v3.py',text))
 old=R/'src/pom_completion_controller_v1.py';text=old.read_text().replace('from pom_namespace_completion_v1 import generation_bindings','from pom_namespace_completion_v1 import generation_bindings\nfrom flatten_output_guard_completion_v1 import source_hashes')
 variants.append((old,R/'src/pom_completion_controller_v2.py',text))
 old=R/'src/complete_maven_groups_v2.py';text=old.read_text().replace('completion_measurement_commands_v2','completion_measurement_commands_v3').replace('pom_completion_controller_v1','pom_completion_controller_v2')
 text=text.replace('from maven_controller_v2 import archive,source_hashes,bytecode,dependency,effective,ensure','from maven_controller_v2 import archive,bytecode,dependency,effective,ensure\nfrom flatten_output_guard_completion_v1 import source_hashes,capture')
 text=text.replace("f'admission_maven_{group}_v1.json'","f'admission_maven_{group}_v2.json'").replace("f'maven_{group}_run_v1'","f'maven_{group}_run_v2'").replace("f'{i:03d}_completion_{group}_v1'","f'{i:03d}_completion_{group}_v2'")
 text=text.replace("old=R/'jobs'/f\"{job['sample_index_1based']:03d}\"", "old=R/'jobs'/('072_completion_pom_v1' if job['sample_index_1based']==72 else f\"{job['sample_index_1based']:03d}\")")
 before="junit_patch(module,out,before)\n after=dependency(commands,args,module,out,'after');effective(commands,args,module,out,'after')"
 after="""if job['sample_index_1based']==72:
  capture(out,'before_measurement')
 else:junit_patch(module,out,before)
 after=dependency(commands,args,module,out,'after');effective(commands,args,module,out,'after')"""
 assert before in text;text=text.replace(before,after)
 before="gate=ns['run_maven_test_command'](str(module),df,'Windows')[0]"
 after="""if job['sample_index_1based']==72:
  gate=ns['run_maven_test_command'](str(module),df,'Windows')[0]
  capture(out,'after_measurement')
 else:
  r=commands.run([*args,'clean','test','jacoco:prepare-agent','jacoco:report'],cwd=module,timeout=300)
  gate=r.returncode==0 and 'BUILD SUCCESS' in r.stdout"""
 assert before in text;text=text.replace(before,after)
 text=text.replace("'configuration':'E1_post_outcome_JUnit3_test_tool_support_v1'","'configuration':'E1_post_outcome_existing_suite_stage_completion_v2'")
 text=text.replace("production=bytecode(module);ensure(production==load(old/'production_generation_baseline.json'),'Production bytecode differs from suite-generation baseline')","production=bytecode(module);baseline=load(old/'production_generation_baseline.json') if (old/'production_generation_baseline.json').exists() else load(A/'stage_completion_v4_preparation/072_generation_bytecode_baseline.json');ensure(production==baseline,'Production bytecode differs from suite-generation baseline')")
 text=text.replace("original=load(old/'before_dependency.json')","original=load(old/'before_dependency.json') if (old/'before_dependency.json').exists() else before")
 text=text.replace("'terminal':True,**raw","'terminal':job['sample_index_1based']==72,'PIT_stage':'attempted' if job['sample_index_1based']==72 else 'UNRESOLVED_PROVIDER_NOT_QUALIFIED; measurement gate is test-only','test_only_process_gate':int(gate) if job['sample_index_1based']!=72 else None,**raw")
 # An admitted one-pass continuation handles 72 without regeneration; remaining 9 as new generation.
 text=text.replace("if group=='pom':\n      from", "if group=='pom' and i!=72:\n      capture(out,'before_generation')\n      from")
 text=text.replace("result=execute(out,job,commands,event)","result=execute(out,job,commands,event);capture(out,'after_generation_and_measurement')")
 variants.append((old,R/'src/complete_maven_groups_v3.py',text))
 for old,new,text in variants:
  ast.parse(text)
  with new.open('x',encoding='utf-8') as f:f.write(text)
  (out/(new.stem+'.diff')).write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
 # 72 stopped immediately after generation; recover its immutable emitted production baseline now.
 old=R/'jobs/072_completion_pom_v1';p=old/'repo/server/target/classes';baseline={x.relative_to(p).as_posix():sha(x) for x in p.rglob('*.class')};assert baseline
 dump(out/'072_generation_bytecode_baseline.json',baseline)
 dump(out/'receipt.json',{'POM72_stop':'only server/.flattened-pom.xml changed, pre-existing flatten plugin output; Java and suite unchanged','POM72_complete_native_suite':load(old/'native_generated.json'),'POM72_regeneration_allowed':False,'remaining_POM_indices':[112,119,163,173,211,220,269,275,294],'JUnit3_fixture_status':'compile, graph equality and native tests PASS; PIT minion UNKNOWN_ERROR, not qualified','JUnit3_benchmark_admission':'compile/test only; PIT remains unresolved; no production dependency change or test edit','post_observed_error_amendment':True,'score_selection':False})
 print('Prepared stage-qualified completion; 72 suite reused, JUnit3 PIT remains unresolved')
if __name__=='__main__':main()
