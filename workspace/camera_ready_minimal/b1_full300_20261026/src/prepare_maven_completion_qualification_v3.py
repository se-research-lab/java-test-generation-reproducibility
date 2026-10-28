"""Add only the legacy java -version probe and absolute Maven executable grammar."""
import ast,difflib,json
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1'
def main():
 out=A/'maven_qualification_v3_preparation';out.mkdir(exist_ok=False);records=[]
 old=R/'src/completion_measurement_commands_v1.py';text=old.read_text()
 before="self.verify_lock();args=list(map(str,argv));assert args[0] in {'mvn','mvn.cmd'},'Only Maven measurement; Java/generation forbidden'\n  cwd=Path(kw['cwd']).resolve();timeout=kw.get('timeout',300)\n  args=self.maven_args(args,cwd,timeout)"
 after="""self.verify_lock();args=list(map(str,argv));cwd=Path(kw.get('cwd',self.out)).resolve();timeout=kw.get('timeout',300)
  if Path(args[0]).name.lower() in {'java','java.exe'}:
   assert args==[str(JDK/'bin/java.exe'),'-version'] and timeout==15,'Java generation forbidden; version probe only'
  else:
   assert Path(args[0]).name.lower() in {'mvn','mvn.cmd'},'Only Maven measurement permitted'
   args=self.maven_args(args,cwd,timeout)"""
 assert before in text;text=text.replace(before,after).replace("self.lock['tool_hashes'][str(MVN.resolve())]","self.lock['tool_hashes'][str(Path(args[0]).resolve())]")
 variants=[(old,R/'src/completion_measurement_commands_v2.py',text)]
 old=R/'src/qualify_maven_completion_v2.py';text=old.read_text().replace('completion_measurement_commands_v1','completion_measurement_commands_v2').replace("('completion_maven_'+kind+'_v2')","('completion_maven_'+kind+'_v3')")
 variants.append((old,R/'src/qualify_maven_completion_v3.py',text))
 old=R/'src/complete_maven_groups_v1.py';text=old.read_text().replace('completion_measurement_commands_v1','completion_measurement_commands_v2')
 variants.append((old,R/'src/complete_maven_groups_v2.py',text))
 old=R/'src/seal_completion_maven_v2.py';text=old.read_text().replace("('completion_maven_'+group+'_v2')","('completion_maven_'+group+'_v3')").replace('completion_measurement_commands_v1','completion_measurement_commands_v2').replace('complete_maven_groups_v1','complete_maven_groups_v2').replace('seal_completion_maven_v2.py','seal_completion_maven_v3.py')
 variants.append((old,R/'src/seal_completion_maven_v3.py',text))
 old=R/'src/run_completion_maven_sequence_v2.py';text=old.read_text().replace("O=A/'maven_sequence_v2'","O=A/'maven_sequence_v3'").replace('qualify_maven_completion_v2.py','qualify_maven_completion_v3.py').replace('seal_completion_maven_v2.py','seal_completion_maven_v3.py').replace('complete_maven_groups_v1.py','complete_maven_groups_v2.py')
 variants.append((old,R/'src/run_completion_maven_sequence_v3.py',text))
 for old,new,text in variants:
  ast.parse(text)
  with new.open('x',encoding='utf-8') as f:f.write(text)
  (out/(new.stem+'.diff')).write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
  records.append({'old':str(old),'old_sha256':sha(old),'new':str(new),'new_sha256':sha(new)})
 dump(out/'receipt.json',{'reason':'legacy measurement helper calls java -version before Maven; previous fixture command grammar rejected this probe and would reject absolute Maven executable','production_compile_and_dependency_audits_passed':True,'benchmark_Maven_classes_started':0,'generation_calls':0,'recipe_versions_targets_mutators_unchanged':True,'native_test_edited':False,'post_diagnostic_fixture_retry':True,'records':records})
 print('New qualification versions prepared; no generation grammar enabled')
if __name__=='__main__':main()
