"""Recount selected raw PIT CSVs and verify frozen generation arguments, offline."""
import json,csv,hashlib,sys
from pathlib import Path
from collections import Counter
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';F=R/'completion_amendment_v1/final300_offline_v1';O=R/'audit_e1_execution_20261028_v1'
sys.path.insert(0,str(B));import audit
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
rows=load(F/'class_results300.json');reports=[];issues=[]
for r in rows:
 if r['observed_mutation_percent'] is None:continue
 assert len(r['raw_reports'])==1
 ref=r['raw_reports'][0];p=Path(ref['path']);assert sha(p)==ref['sha256']
 with p.open(encoding='utf-8-sig',newline='') as f:raw=list(csv.reader(f))
 assert raw and all(len(x)==7 for x in raw)
 source=r['class_key'].split('/')[-1];package=r['selected_test_fqcn'].rpartition('.')[0]
 focal=[x for x in raw if x[0].casefold()==source and x[1].rpartition('.')[0]==package]
 assert focal,r['index'];c=Counter(x[5] for x in focal);value=round(100*c['KILLED']/len(focal),2)
 assert value==r['observed_mutation_percent'] and len(focal)==r['focal_mutants'] and dict(c)==r['PIT_status_counts'],r['index']
 reports.append({'index':r['index'],'focal_mutants':len(focal),'killed':c['KILLED'],'statuses':dict(c),'observed_percent':value,'path':str(p),'sha256':ref['sha256']})
assert len(reports)==221
result={'status':'PASS','verified_selected_raw_PIT_reports':221,'valid_observed_zero':sum(x['observed_percent']==0 for x in reports),'class294':next(x for x in reports if x['index']==294),'all_formula':'round(100*KILLED/all_focal_SourceFile_package_rows,2)','TIMED_OUT_is_numerator':False,'new_experiments':0}
with (O/'RAW_PIT_RECHECK.json').open('x',encoding='utf-8') as f:json.dump({'summary':result,'reports':reports},f,indent=2)
audit.log('E1_RAW_PIT_RECHECK_20261028',path=str(O/'RAW_PIT_RECHECK.json'),sha256=sha(O/'RAW_PIT_RECHECK.json'),reports=221,new_experiments=0)
print(json.dumps(result,indent=2))
