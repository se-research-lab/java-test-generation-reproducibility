"""Read-only evidence census. Writes a NEW amendment audit, never launches experiments."""
import csv,difflib,hashlib,json,subprocess,sys
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump

A=R/'completion_amendment_v1'
POM={72,112,119,163,173,211,220,269,275,294}
J3={48,49,128,138,145,148,198,202,224,239}
PIT={4,40,45,129,135,156,169,170,184,197}
TASK={98,110,161,199,207,227,241,251,264,268}
EVID={6,10,17,52,58,60,74,108,132,137,150,160,247,250,261,289}

def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def pin(p):return {'path':str(Path(p).resolve()),'sha256':sha(p)}
def git(j,rel):
 p=R.parents[1]/'compiledrepos'/j['repo_id']
 cmd=['git','-c','safe.directory='+p.as_posix(),'-C',str(p),'show',j['commit_sha']+':'+rel]
 q=subprocess.run(cmd,capture_output=True,timeout=30)
 return cmd,q
def xml(b):
 try:return {'parseable':True,'root':ET.fromstring(b).tag}
 except ET.ParseError as e:return {'parseable':False,'error':str(e)}
def main():
 out=A/'input_audit';out.mkdir(parents=True,exist_ok=False)
 jobs=load(R/'manifest300.json');old=load(R/'analysis_camera_ready_rq45_v1/class_evidence300.json')
 assert len(jobs)==len(old)==300 and len({j['class_key'] for j in jobs})==300
 snapshots={i:R/x['manifest'] for x in load(R/'inputs/snapshot_v3/index.json') for i in x['class_indices']}
 context={x['sample_index_1based']:x for x in load(R/'inputs/context251_v1/manifest.json')}
 hist=R.parents[1]/'scripts_v2/results/runs/full300_merged_20260724_paper'
 rows=[];pins={str((R/'manifest300.json').resolve()):sha(R/'manifest300.json')}
 for f in [hist/'metrics_long.csv',hist/'generation_classes.csv',R/'analysis_camera_ready_rq45_v1/historical_arm_scoped_evidence600.json',R/'analysis_camera_ready_rq45_v1/class_evidence300.json']:
  pins[str(f.resolve())]=sha(f)
 for j,o in zip(jobs,old):
  i=j['sample_index_1based'];assert i==o['index'] and j['class_key']==o['class_key']
  row={'index':i,'class_key':j['class_key'],'repo_id':j['repo_id'],'commit_sha':j['commit_sha'],'seed':j['seed'],'build_tool':j['build_tool'],'historical':{k:v for k,v in o.items() if k.startswith(('G0_','E0_'))},'previous_E1':o,'groups':[],'evidence':[]}
  for name,s in [('POM_INPUT',POM),('JUNIT3_SUPPORT',J3),('PIT_TOOL_RESOLUTION',PIT),('GRADLE_TASK_REGISTRATION',TASK),('MEASUREMENT_EVIDENCE_REVIEW',EVID)]:
   if i in s:row['groups'].append(name)
  source=Path(j['source_candidate']['source_repo']);focal=source/j['focal_path'];row['source_focal']=pin(focal)
  assert sha(focal)==j['source_candidate']['focal_sha256']
  if j['build_tool']=='maven':
   pom=source/j['module']/'pom.xml'
   row['module_pom']={**pin(pom),**xml(pom.read_bytes())}
  p=Path(o['E1_result_path']) if o.get('E1_result_path') else None
  folder=p.parent if p and p.is_file() else R/'jobs'/(f'{i:03d}_gradle_v1' if j['build_tool']=='gradle' else f'{i:03d}')
  row['prior_job']=str(folder)
  if p and p.is_file():row['result_pin']=pin(p);pins[str(p.resolve())]=sha(p)
  before=folder/'before_dependency.json'
  if before.is_file():
   d=load(before);row['resolved_junit_before']=[r for r in d['classpath'] if r['path'].startswith('junit/junit/')];row['production_junit_before']=[r for r in d['compile_classpath'] if r['path'].startswith('junit/junit/')]
  if i in POM:
   d=out/'pom_provenance'/f'{i:03d}';d.mkdir(parents=True)
   cmd,q=git(j,j['module']+'/pom.xml');assert q.returncode==0,q.stderr
   cp=d/'commit_pom.xml';cp.write_bytes(q.stdout)
   oldp=d/'frozen_input_pom.xml';oldp.write_bytes(pom.read_bytes())
   cmdf,qf=git(j,j['focal_path']);assert qf.returncode==0
   # Git stores LF; original checkout may have CRLF. Compare content, retain byte hashes.
   normalize=lambda b:b.replace(b'\r\n',b'\n')
   focal_equal=normalize(qf.stdout)==normalize(focal.read_bytes())
   assert focal_equal,'Focal source not equivalent to sampled commit'
   candidates=[]
   for c in j['source_candidates']:
    x=Path(c['source_repo'])/j['module']/'pom.xml'
    if x.is_file():candidates.append({**pin(x),**xml(x.read_bytes()),'commit_equal_except_EOL':normalize(x.read_bytes())==normalize(q.stdout)})
   diff=d/'commit_to_frozen.diff';diff.write_text(''.join(difflib.unified_diff(q.stdout.decode().splitlines(True),pom.read_text().splitlines(True),fromfile='sampled_commit/pom.xml',tofile='historical_prepared/pom.xml')),encoding='utf-8')
   row['pom_provenance']={'git_read_command':cmd,'commit_pom':pin(cp),'frozen_pom':pin(oldp),'commit_xml':xml(q.stdout),'focal_matches_commit_except_EOL':focal_equal,'git_focal_sha256':hashlib.sha256(qf.stdout).hexdigest(),'candidates':candidates,'diff':pin(diff),'classification':'HISTORICAL_PREPARATION_INPUT_CORRUPTION_NOT_EVO_GENERATION_FAILURE'}
  if row['groups']:
   for f in ['native_generated.json','before_dependency.json','before_effective_pom.xml','before_tree.txt','production_generation_baseline.json','interrupted.json','deferred.json','result.json','artifact_manifest.json','generation_classpath_rule.json']:
    if (folder/f).is_file():row['evidence'].append(pin(folder/f))
   commands=[]
   for plan in sorted((folder/'commands').glob('*/plan.json')):
    x=load(plan);commands.append({'plan':pin(plan),'argv':x.get('argv'),'started':(plan.parent/'started.json').is_file(),'logs':[pin(plan.parent/n) for n in ['stdout.txt','stderr.txt','finished.json'] if (plan.parent/n).is_file()]})
   row['commands']=commands
   row['native_suite_pins']=load(folder/'native_generated.json').get('files',[]) if (folder/'native_generated.json').exists() else []
   for f in row['native_suite_pins']:assert sha(f['path'])==f['sha256']
  if i in EVID:
   raw=load(p);module=folder/'repo'/j['module'];reports=list((module/'target/pit-reports').rglob('mutations.csv'))
   # E49 uses a separate working-copy convention; no inference from absence.
   if not reports:reports=list(folder.glob('**/mutations.csv'))
   pitrows=[]
   for report in reports:
    with report.open(encoding='utf-8-sig',newline='') as f: rr=list(csv.reader(f))
    pitrows.append({'report':pin(report),'rows':len(rr),'status_counts':dict(Counter(x[5] for x in rr if len(x)==7)),'all_rows_have_7_columns':all(len(x)==7 for x in rr)})
   row['measurement_review']={'suite_evidence':raw.get('strict_suite_evidence'),'mutants':raw.get('focal_mutants'),'observed_report_score':raw.get('mutation_score_percent'),'jacoco_focal_rows':raw.get('jacoco_focal_rows'),'cases':raw.get('cases'),'PIT_reports':pitrows,'reason_not_strict_evidence':('no_positive_unskipped_suite' if not raw.get('strict_suite_evidence') else 'no_focal_mutants' if not raw.get('focal_mutants') else 'missing_JaCoCo_focal_row_not_missing_PIT_report'),'automatic_rerun':False}
  rows.append(row)
 dump(out/'class_census300.json',rows)
 malformed=[r['index'] for r in rows if r.get('module_pom',{}).get('parseable') is False]
 junit3=[r['index'] for r in rows if any(not x['path'].split('/')[2].startswith('4.') for x in r.get('resolved_junit_before',[]))]
 summary={'created_utc':datetime.now(timezone.utc).isoformat(),'status':'INPUT_REVIEW_ONLY_NO_BENCHMARK_ADMISSION','n':300,'prior_terminal':sum(r['previous_E1']['E1_build'] is not None for r in rows),'malformed_module_POM_all300':malformed,'resolved_non_JUnit4_all_available_jobs':junit3,'POM_candidates_exactly_cover_census':set(malformed)==POM,'JUnit3_candidates_exactly_cover_census':set(junit3)==J3,'groups':{k:[r['index'] for r in rows if k in r['groups']] for k in ['POM_INPUT','JUNIT3_SUPPORT','PIT_TOOL_RESOLUTION','GRADLE_TASK_REGISTRATION','MEASUREMENT_EVIDENCE_REVIEW']},'new_experiment_calls':0,'GPT_API_calls':0,'post_outcome_amendment':True}
 dump(out/'summary.json',summary);dump(out/'baseline_pins.json',pins)
 print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
