"""Pure preparation of a Gradle-specific EvoSuite command guard; no admission."""
import ast,difflib,sys
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
out=R/'audit/gradle_generation_guard_v1';out.mkdir(exist_ok=False)
origin=R/'src/maven_adapter_v1.py';source=origin.read_text(encoding='utf-8');tree=ast.parse(source)
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='checked_generation_argv')
body=ast.get_source_segment(source,node)
replacement=body.replace('def checked_generation_argv(', 'def checked_gradle_generation_argv(').replace("job['build_tool']!='maven'", "job['build_tool']!='gradle'").replace('Maven adapter cannot admit Gradle','Gradle adapter cannot admit Maven')
assert replacement.replace('def checked_gradle_generation_argv(', 'def checked_generation_argv(').replace("job['build_tool']!='gradle'", "job['build_tool']!='maven'").replace('Gradle adapter cannot admit Maven','Maven adapter cannot admit Gradle')==body
new=R/'src/gradle_generation_argv_v1.py'
text='''"""Gradle-specific profile/seed guard, E49-identical except build-tool label.
No launcher. A qualified controller must bind CP to the ordered Gradle audit.
"""
from pathlib import Path
from maven_adapter_v1 import R,JDK,WORKSPACE,GuardAbort,new_job_output,reviewer_options
\n'''+replacement+'\n'
ast.parse(text)
with new.open('x',encoding='utf-8') as f:f.write(text)
dump(out/'extraction.json',{'status':'PASS_EXACT_BODY_EXCEPT_BUILD_TOOL_AND_NAME','source':str(origin),'source_sha256':sha(origin),'target':str(new),'target_sha256':sha(new),'changes':['function name','explicit build_tool guard maven to gradle','guard error message'],'generation_flags_seed_budget_logic_unchanged':True,'execution_admitted':False,'new_EvoSuite_calls':0,'GPT_API_calls':0})
audit.log('B1_GRADLE_GENERATION_ARGV_GUARD_PREPARED',extraction_sha256=sha(out/'extraction.json'),new_EvoSuite_calls=0,GPT_API_calls=0)
print('PASS pure guard extraction: generation option and seed validation unchanged')
