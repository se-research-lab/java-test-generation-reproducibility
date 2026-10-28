import json,subprocess,sys,psutil
from maven_adapter_v1 import R,sha,dump
A=R/'completion_amendment_v1'
def main():
 out=A/'preview_v2';assert not (out/'owner.json').exists();old=json.loads((A/'preview_v1/owner.json').read_text());p=psutil.Process(old['pid'])
 assert p.create_time()==old['create_time'] and any(x.endswith('serve_completion_preview_v1.py') for x in p.cmdline())
 children=[{'pid':c.pid,'create_time':c.create_time(),'name':c.name()} for c in p.children(recursive=True)];assert all(x['name'].lower()=='conhost.exe' for x in children)
 dump(out/'restart_scope.json',{'old_owner':old,'children':children,'reason':'initial restart guard refused hidden console helper; no benchmark descendants','benchmark_terminated':False})
 p.terminate();p.wait(15);script=R/'src/serve_completion_preview_v2.py'
 with (out/'stdout.txt').open('xb') as so,(out/'stderr.txt').open('xb') as se:child=subprocess.Popen([sys.executable,'-B','-X','utf8',str(script)],stdout=so,stderr=se,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW,cwd=R)
 dump(out/'owner.json',{'pid':child.pid,'create_time':psutil.Process(child.pid).create_time(),'script_sha256':sha(script),'url':'http://127.0.0.1:8767/','read_only':True,'experimental_code_changed':False})
 print('Read-only preview v2 started; experiment unaffected')
if __name__=='__main__':main()
