"""Display-only: include new POM namespace and explicitly rejected timeout reports."""
import ast,difflib,json,subprocess,sys,psutil
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1'
def main():
 old=R/'src/serve_completion_preview_v1.py';new=R/'src/serve_completion_preview_v2.py';t=old.read_text()
 t=t.replace("if group=='pom':folders+=list((R/'jobs').glob('*_completion_pom_v1'))","if group=='pom':folders+=list((R/'jobs').glob('*_completion_pom_v1'))+list((R/'jobs').glob('*_completion_pom_v3'))")
 t=t.replace("  for i,d in selected.items():","  if group=='pom' and (A/'result_reconciliations_v1/112/result.json').exists():selected[112]=load(A/'result_reconciliations_v1/112/result.json')\n  for i,d in selected.items():")
 t=t.replace("pit='có' if d.get('pit_report_present') else 'chưa có'","pit=('partial/timeout — rejected' if d.get('PIT_report_complete') is False and d.get('pit_report_present') else 'có' if d.get('pit_report_present') else 'chưa có')")
 t=t.replace("['maven_junit3_run_v2','maven_pom_run_v2','gradle_pit_run_v2']","['maven_junit3_run_v2','maven_pom_run_v2','maven_pom_run_v3','gradle_pit_run_v2']")
 ast.parse(t)
 with new.open('x',encoding='utf-8') as f:f.write(t)
 out=A/'preview_v2';out.mkdir(exist_ok=False);(out/'display.diff').write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),t.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
 oldowner=json.loads((A/'preview_v1/owner.json').read_text());p=psutil.Process(oldowner['pid']);assert p.create_time()==oldowner['create_time'];assert any(x.endswith('serve_completion_preview_v1.py') for x in p.cmdline());assert not p.children()
 p.terminate();p.wait(15)
 with (out/'stdout.txt').open('xb') as so,(out/'stderr.txt').open('xb') as se:child=subprocess.Popen([sys.executable,'-B','-X','utf8',str(new)],stdout=so,stderr=se,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW,cwd=R)
 dump(out/'owner.json',{'pid':child.pid,'create_time':psutil.Process(child.pid).create_time(),'url':'http://127.0.0.1:8767/','script_sha256':sha(new),'read_only':True,'experimental_code_changed':False,'old_preview_owner':oldowner})
 print('Display refreshed at same loopback URL; benchmark worker untouched')
if __name__=='__main__':main()
