"""Prepare new synthetic qualification runners, preserving old fixtures."""
from pathlib import Path
import ast,difflib,sys
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1'
def main():
 old=R/'src/run_gradle_native_fixture_v7.py';new=R/'src/qualify_gradle_tool_repository_amendment_v1.py'
 text=old.read_text(encoding='utf-8')
 text=text.replace('from gradle_native_recipe_v7 import write_recipe,VERSIONS,groovy','from gradle_tool_repository_amendment_v1 import write_recipe,VERSIONS,groovy')
 text=text.replace('gradle_native_runtime_fixture_v7','gradle_tool_repository_amendment_fixture_v1')
 text=text.replace("buildscript { repositories { mavenCentral() } }\\n",'')
 text=text.replace("pinpaths=[Path(__file__),","pinpaths=[Path(__file__),R/'src/gradle_tool_repository_amendment_v1.py',")
 ast.parse(text)
 with new.open('x',encoding='utf-8') as f:f.write(text)
 out=A/'qualification_preparation';out.mkdir(exist_ok=False)
 (out/'fixture.diff').write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
 dump(out/'receipt.json',{'old_fixture_sha256':sha(old),'new_fixture_sha256':sha(new),'amendment_sha256':sha(R/'src/gradle_tool_repository_amendment_v1.py'),'purpose':'same saved synthetic suite, no buildscript repository in fixture source; validate adapter supplies tool resolution only','new_generation_calls':0,'post_outcome':True})
 print('Prepared synthetic-only qualification; no benchmark started')
if __name__=='__main__':main()
