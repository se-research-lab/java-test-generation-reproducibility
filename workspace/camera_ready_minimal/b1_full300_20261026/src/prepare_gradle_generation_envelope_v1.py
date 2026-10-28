"""Add an explicit, independently guarded Java generation stage to Gradle.
Pure source preparation only; no fixture or corpus command is launched.
"""
import ast,difflib,sys
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
out=R/'audit/gradle_generation_envelope_v1';out.mkdir(exist_ok=False);changes=[]
def write(old,new,text):
 ast.parse(text)
 with new.open('x',encoding='utf-8') as f:f.write(text)
 diff=out/(new.stem+'.diff');diff.write_text(''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
 changes.append({'old_path':str(old),'old_sha256':sha(old),'new_path':str(new),'new_sha256':sha(new),'diff_sha256':sha(diff)})
old=R/'src/gradle_command_policy_v2.py';new=R/'src/gradle_command_policy_v3.py';text=old.read_text(encoding='utf-8')
text=text.replace("ensure(cwd==self.build_root and cwd.is_dir(),'Cwd must be exact owned metadata build root')", "ensure(cwd==(self.module if stage=='generation' else self.build_root) and cwd.is_dir(),'Cwd must match exact metadata module for generation, build root otherwise')")
before="""   ensure(qualification and stage=='java_version' and tail==['-version'] and timeout==15,'Prototype Java permits qualification -version only; EvoSuite guard not wired')
   expected=[str(exe),'-version']"""
after="""   if stage=='generation':
    ensure(timeout==240,'Generation timeout must remain240 seconds')
    from gradle_generation_plan_guard_v1 import validate as validate_generation
    validate_generation(args,self.job,self.context,self.out,self.lock)
    expected=[str(exe),*tail]
   else:
    ensure(qualification and stage=='java_version' and tail==['-version'] and timeout==15,'Java command outside declared generation/version grammar')
    expected=[str(exe),'-version']"""
assert text.count(before)==1;text=text.replace(before,after);write(old,new,text)
old=R/'src/gradle_process_supervisor_v3.py';new=R/'src/gradle_process_supervisor_v4.py';text=old.read_text(encoding='utf-8').replace('gradle_command_policy_v2','gradle_command_policy_v3').replace('B1_gradle_supervisor_v3','B1_gradle_supervisor_v4').replace('gradle_guard_v3','gradle_guard_v4');write(old,new,text)
dump(out/'preparation.json',{'scope':'pure preparation, no admission','changes':changes,'generation_guard_sha256':sha(R/'src/gradle_generation_plan_guard_v1.py'),'profile_guard_sha256':sha(R/'src/gradle_generation_argv_v1.py'),'existing_Gradle_task_validation_unchanged':True,'new_Java_stage':'exact declared240s command; pinned ordered CP; E49 profile+seed; max2 same-seed technical sanitizer attempts; CP-file inverse proof','no_test_source_repair':True,'no_score_retry':True,'benchmark_admitted':False,'new_EvoSuite_calls':0,'GPT_API_calls':0})
audit.log('B1_GRADLE_GENERATION_ENVELOPE_PREPARED',receipt_sha256=sha(out/'preparation.json'),execution_admitted=False)
print('PASS pure envelope preparation; execution still requires qualification/admission')
