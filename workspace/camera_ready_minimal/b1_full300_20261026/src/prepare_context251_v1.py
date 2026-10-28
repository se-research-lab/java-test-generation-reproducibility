"""Freeze historical framework/context metadata without invoking any project code."""
import csv,json,re,shutil,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def load(p):return json.loads(p.read_text(encoding='utf-8'))
jobs=load(R/'manifest300.json');source=R.parents[1]/'scripts_v2/results/runs/full300_merged_20260724_paper/generation_classes.csv'
with source.open(encoding='utf-8-sig',newline='') as f:historical={r['class_key']:r for r in csv.DictReader(f)}
out=R/'inputs/context251_v1';out.mkdir(parents=True,exist_ok=False);rows=[];copied={}
for j in jobs:
 if j['reused_result']:continue
 root=Path(j['source_candidate']['source_repo']);infofile=root.parent.parent/'output/project_info.json';csfile=root.parent.parent/'output/classes.csv';key=j['repo_id']+'_'+j['module'] if j['module'] else j['repo_id']
 info=load(infofile) if infofile.is_file() else {};framework=info.get(key);notes=[]
 record={'sample_index_1based':j['sample_index_1based'],'class_key':j['class_key'],'module':j['module'],'framework_key':key,'framework_found':framework is not None,'junit_version':framework.get('junit_version') if framework else None,'testng_version':framework.get('testng_version') if framework else None,'compiler_version':framework.get('compiler_version') if framework else None,'metadata_sources':[]}
 for p in [infofile,csfile]:
  if not p.is_file():notes.append('missing '+p.name);continue
  h=audit.sha(p);dest=out/'blobs'/h
  if h not in copied:
   dest.parent.mkdir(parents=True,exist_ok=True)
   with p.open('rb') as f,dest.open('xb') as t:shutil.copyfileobj(f,t)
   assert audit.sha(dest)==h;copied[h]=str(dest.relative_to(R))
  record['metadata_sources'].append({'path':str(p),'sha256':h,'backup':copied[h]})
 original=historical[j['class_key']];prior=original['Synthesized_Test_Rel_Path'];assert not Path(prior).is_absolute() and '..' not in Path(prior).parts
 focal=root/j['focal_path'];assert audit.sha(focal)==j['source_candidate']['focal_sha256']
 m=re.search(r'^\s*package\s+([\w.$]+)\s*;',focal.read_text(encoding='utf-8-sig',errors='replace'),re.M);package=m.group(1) if m else ''
 record.update(package=package,selected_test_fqcn=(package+'.' if package else '')+j['focal_class']+'_ESTest',prior_synthesized_test_relative=prior,prior_synthesized_test_present=(root/prior).is_file(),notes=notes)
 record['status']='METADATA_FROZEN_NOT_ADMITTED' if framework else 'FRAMEWORK_CONTEXT_UNRESOLVED'
 rows.append(record)
with (out/'manifest.json').open('x',encoding='utf-8') as f:json.dump(rows,f,ensure_ascii=False,indent=2)
summary={'n':len(rows),'framework_found':sum(r['framework_found'] for r in rows),'unresolved_indices':[r['sample_index_1based'] for r in rows if not r['framework_found']],'prior_synthesized_tests_present':sum(r['prior_synthesized_test_present'] for r in rows),'source_csv_sha256':audit.sha(source),'manifest_sha256':audit.sha(out/'manifest.json'),'metadata_blob_count':len(copied),'experiment_calls':0}
with (out/'summary.json').open('x',encoding='utf-8') as f:json.dump(summary,f,indent=2)
audit.log('B1_CONTEXT251_FROZEN',**summary);print(json.dumps(summary,indent=2))
