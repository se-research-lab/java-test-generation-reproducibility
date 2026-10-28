"""Metadata-only source census and adapter backup. No build or generator calls."""
import hashlib,json,os,shutil
from pathlib import Path
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1]
B=R.parent/'paired49_20261023'
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def dump(p,x):
 p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2)
jobs=json.loads((R/'manifest300.json').read_text(encoding='utf-8'))
roots={}
for j in jobs:
 if j['reused_result']:continue
 roots.setdefault(j['source_candidate']['source_repo'],[]).append(j['sample_index_1based'])
inventories=[]
for source,indices in roots.items():
 root=Path(source);files=[];excluded=[];descriptors=[]
 for parent,dirs,names in os.walk(root,followlinks=False):
  p=Path(parent);parts=p.relative_to(root).parts
  for d in dirs[:]:
   q=p/d
   if q.is_symlink() or d in {'.git','.gradle','.idea','node_modules','__pycache__'} or (d in {'target','build'} and 'src' not in parts):
    excluded.append(q.relative_to(root).as_posix());dirs.remove(d)
  for n in names:
   q=p/n;rel=q.relative_to(root).as_posix()
   if q.is_symlink():excluded.append(rel);continue
   files.append({'path':rel,'bytes':q.stat().st_size})
   if n in {'pom.xml','build.gradle','build.gradle.kts','settings.gradle','settings.gradle.kts','gradle.properties','gradle-wrapper.properties'}:
    content=q.read_text(encoding='utf-8',errors='replace')
    descriptors.append({'path':rel,'sha256':sha(q),'bytes':q.stat().st_size,'mentions_TestNG':'testng' in content.lower(),'mentions_useJUnit':'useJUnit' in content,'mentions_evosuite':'evosuite' in content.lower()})
 inventories.append({'source_repo':source,'class_indices':indices,'file_count':len(files),'bytes':sum(x['bytes'] for x in files),'excluded_output_or_tool_directories':excluded,'files':files,'build_descriptors':descriptors,'whole_source_hash_frozen':False,'snapshot_backup_created':False})
dump(R/'audit/source_census_v1.json',inventories)
backup=[]
for rel in ['src/e49_driver.py','src/run_e49_supplement.py','src/replay_fixed49_measurement_v5.py','src/diagnose_e1_compatibility_v4.py','src/analyze_e49_final_v2.py','src/junit_method_inventory.py','evo_patch/working/AgoneTest/mavenLib.py','evo_patch/working/AgoneTest/evosuite_profile.py']:
 source=B/rel
 if not source.is_file():raise FileNotFoundError(source)
 dest=R/'backups/accepted49_adapter'/rel;dest.parent.mkdir(parents=True,exist_ok=True)
 with source.open('rb') as src,dest.open('xb') as out:shutil.copyfileobj(src,out)
 assert sha(dest)==sha(source)
 backup.append({'original':str(source),'backup':str(dest),'sha256':sha(source)})
dump(R/'audit/adapter_backup_manifest_v1.json',backup)
summary={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'unique_candidate_roots':len(roots),'class_count':sum(len(v) for v in roots.values()),'candidate_files':sum(x['file_count'] for x in inventories),'candidate_bytes':sum(x['bytes'] for x in inventories),'candidate_GB':round(sum(x['bytes'] for x in inventories)/1e9,3),'backup_adapter_files':len(backup),'disk_free_GB':round(shutil.disk_usage(R).free/1e9,2),'scope':'metadata census and exact adapter backup only; source snapshots and execution adapter not ready','new_experiment_calls':0}
dump(R/'audit/source_census_summary_v1.json',summary)
with (R/'events.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'kind':'SOURCE_CENSUS_AND_ADAPTER_BACKUP','data':summary},ensure_ascii=False)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
