"""Read-only cache size inventory before planning a workspace-owned cache."""
import os,json,sys,time
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
start=time.monotonic();groups=[]
root=Path('C:/Users/admin/.m2/repository')
for group in root.iterdir():
    if not group.is_dir():continue
    n=size=0
    for d,dirs,files in os.walk(group):
        dirs[:]=[x for x in dirs if not Path(d,x).is_symlink()]
        for name in files:
            p=Path(d,name)
            if not p.is_symlink():n+=1;size+=p.stat().st_size
    groups.append({'group':group.name,'files':n,'bytes':size})
report={'groups':groups,'files':sum(x['files'] for x in groups),'bytes':sum(x['bytes'] for x in groups),'seconds':time.monotonic()-start,'read_only':True}
p=BASE/'e49_driver/cache_inventory.json';p.parent.mkdir(exist_ok=True)
with p.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
audit.log('CACHE_READONLY_INVENTORY',sha256=audit.sha(p),bytes=report['bytes'],files=report['files'])
print(json.dumps({k:v for k,v in report.items() if k!='groups'},indent=2))
