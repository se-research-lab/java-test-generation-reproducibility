"""Read-only ongoing raw checks; never aggregates partial outcomes or emits final results."""
import json,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));sys.path.insert(0,str(BASE/'src'))
import audit,analyze_e49_final_v1 as a
jobs=a.read(a.STAGE/'input_manifest49.json');g=a.csvread(BASE/'outputs/paired49.csv');checked=[]
for j,f in zip(jobs[:17],g[:17]):
    idx=j['job_index'];row=a.read(a.STAGE/('job_result_%02d.json'%idx))
    _,diag=a.inspect_job(j,f,row,a.STAGE/'archive_final_v4')
    checked.append({'class_key':j['class_key'],'job_index':idx,'archive_files_verified':diag['archive_files_verified'],'PIT_killing_suite_check':diag['PIT_killing_suite_check']})
report={'status':'PASS','checked':len(checked),'expected_final_n':49,'final_result_emitted':False,'partial_means_computed':False,'rows':checked,'analyzer_sha256':audit.sha(BASE/'src/analyze_e49_final_v1.py')}
p=BASE/'validation/e49_raw_prefix17.json'
with p.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
audit.log('E49_RAW_PREFIX_READONLY_CHECK',n=17,final_result_emitted=False,sha256=audit.sha(p))
print(json.dumps({'status':'PASS','raw_jobs_checked':17,'final_result_emitted':False}))
