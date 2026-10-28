"""Read-only display update for the user-authorized five-class resume namespace."""
import ast,difflib,json,sys,subprocess,psutil
from datetime import datetime,timezone
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
from projection_io_v1 import publish_json
A=R/'completion_amendment_v1';O=A/'preview_v3'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
 old=R/'src/serve_completion_preview_v2.py';new=R/'src/serve_completion_preview_v3.py';text=old.read_text()
 before="if group=='pom':folders+=list((R/'jobs').glob('*_completion_pom_v1'))+list((R/'jobs').glob('*_completion_pom_v3'))"
 assert text.count(before)==1;text=text.replace(before,before+"+list((R/'jobs').glob('*_completion_pom_resume_after173_v1'))")
 text=text.replace("'maven_pom_run_v3','gradle_pit_run_v2'","'maven_pom_run_v3','maven_pom_resume_after173_v1','gradle_pit_run_v2'")
 text=text.replace("'72 suite cũ; còn lại generation nếu chưa có'","'resume211/220/269/275/294; 25 checkpoint giữ nguyên'")
 ast.parse(text)
 with new.open('x',encoding='utf-8') as f:f.write(text)
 O.mkdir(exist_ok=False);(O/'display_only.diff').write_text(''.join(difflib.unified_diff(old.read_text().splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
 oldowner=load(A/'preview_v2/owner.json');p=psutil.Process(oldowner['pid']);assert p.create_time()==oldowner['create_time'];assert any(x.endswith('serve_completion_preview_v2.py') for x in p.cmdline());assert all(x.name().lower()=='conhost.exe' for x in p.children(recursive=True))
 p.terminate();p.wait(15)
 with (O/'stdout.txt').open('xb') as so,(O/'stderr.txt').open('xb') as se:child=subprocess.Popen([sys.executable,'-B','-X','utf8',str(new)],stdout=so,stderr=se,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW,cwd=R)
 dump(O/'owner.json',{'pid':child.pid,'create_time':psutil.Process(child.pid).create_time(),'script_sha256':sha(new),'url':'http://127.0.0.1:8767/','read_only':True,'benchmark_process_terminated':False})
 progress=load(R/'runtime/completion_progress.json')
 if progress.get('phase')=='PAUSED_BY_USER_AFTER_VERIFIED173':
  checkpoint=load(A/'pause_20261027_after173_v1/checkpoint.json')
  publish_json(R/'runtime/completion_progress.json',{'phase':'RESUMED_BY_USER_PREPARING211','active_index':211,'previous_accepted_indices':checkpoint['accepted25_indices'],'remaining_indices':[211,220,269,275,294],'updated_utc':datetime.now(timezone.utc).isoformat(),'GPT_API_calls':0,'policy_seed_config_changed':False,'full300_complete':False,'follow_on_queues_enabled':False},label='explicit_resume_preview')
 print('Preview updated for remaining-five resume; scientific code unchanged')
if __name__=='__main__':main()
