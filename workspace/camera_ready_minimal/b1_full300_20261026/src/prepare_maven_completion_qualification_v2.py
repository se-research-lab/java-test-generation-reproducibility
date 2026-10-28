"""Preserve failed synthetic qualifications; correct pin scope and runtime-JAR inventory."""
import ast,difflib,json
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1'
def main():
 out=A/'maven_qualification_v2_preparation';out.mkdir(exist_ok=False)
 old=R/'src/qualify_maven_completion_v1.py';new=R/'src/qualify_maven_completion_v2.py';text=old.read_text()
 text=text.replace("('completion_maven_'+kind+'_v1')","('completion_maven_'+kind+'_v2')")
 before="codes=list((R/'src').glob('*.py'));pins={str(p.resolve()):sha(p) for p in codes}"
 after="pins=load(R/'admission_maven_v6.json')['code_and_input_hashes'].copy()\n codes=[Path(__file__),R/'src/pom_namespace_completion_v1.py',R/'src/junit3_test_support_completion_v1.py',R/'src/completion_measurement_commands_v1.py']\n pins.update({str(p.resolve()):sha(p) for p in codes})"
 assert before in text;text=text.replace(before,after)
 text=text.replace("[MVN,JDK/'bin/java.exe',JDK/'lib/tools.jar']","[MVN,JDK/'bin/java.exe',JDK/'lib/tools.jar',R.parents[1]/'scripts_v2/evosuite-standalone-runtime-1.2.0.jar']")
 variants=[(old,new,text)]
 oldseal=R/'src/seal_completion_maven_v1.py';newseal=R/'src/seal_completion_maven_v2.py'
 st=oldseal.read_text().replace("('completion_maven_'+group+'_v1')","('completion_maven_'+group+'_v2')").replace("'seal_completion_maven_v1.py'","'seal_completion_maven_v2.py'")
 variants.append((oldseal,newseal,st))
 oldseq=R/'src/run_completion_maven_sequence_v1.py';newseq=R/'src/run_completion_maven_sequence_v2.py'
 seq=oldseq.read_text().replace("O=A/'maven_sequence_v1'","O=A/'maven_sequence_v2'").replace('qualify_maven_completion_v1.py','qualify_maven_completion_v2.py').replace('seal_completion_maven_v1.py','seal_completion_maven_v2.py')
 variants.append((oldseq,newseq,seq));records=[]
 for old,new,text in variants:
  ast.parse(text)
  with new.open('x',encoding='utf-8') as f:f.write(text)
  (out/(new.stem+'.diff')).write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
  records.append({'old':str(old),'old_sha256':sha(old),'new':str(new),'new_sha256':sha(new)})
 dump(out/'receipt.json',{'purpose':'synthetic qualification harness correction only','POM_first_fixture':'production compile passed; subsequent audit stopped on unrelated analytics source hash changed during fixture','JUnit3_first_fixture':'production compile and dependency commands ran; audit stopped because existing EvoSuite runtime jar absent in fixture tool pin inventory','benchmark_Maven_classes_started':0,'generation_calls':0,'test_source_changed':False,'experimental_adapter_changed':False,'records':records,'post_diagnostic_qualification_retry':True,'not_prespecified_benchmark_retry':True})
 print('Prepared new fixture namespace; pinned execution dependencies and existing runtime JAR; old evidence retained')
if __name__=='__main__':main()
