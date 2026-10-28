"""Late comparison only; raw audit has already completed all49 without official output."""
import importlib.util,json,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
SOURCE=BASE/'src/independent_measurement49_raw_audit_v3.py'
def main():
    assert audit.sha(SOURCE)=='38ab0d3c34b7be5a0247c7b405aaa92792a39665e18ca68ad732f6f3973d0c19'
    spec=importlib.util.spec_from_file_location('late_compare_readonly_auditor',SOURCE);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    rawdir=BASE/'validation/independent_compat49_raw_v1';official=BASE/'outputs/e49_measurement_compat_v1'
    original=m.read(rawdir/'audit.json');rows=m.read(rawdir/'raw_reconstructed49.json');assert original['status']=='PASS' and original['n']==49 and original['official_comparison']['status']=='NOT_YET_PRESENT'
    assert len(rows)==49;stats,indices,values=m.summaries(rows);assert stats==original['statistics'],'Raw reconstruction/math changed'
    comparison=m.compare_official(official,rows,stats,indices,values);assert comparison['status']=='PASS' and comparison['all20000_draws_match'] and comparison['fixed49_rows_match']
    out=BASE/'validation/independent_compat49_late_comparison_v1';out.mkdir(exist_ok=False)
    inputs=[rawdir/'audit.json',rawdir/'raw_reconstructed49.json',rawdir/'output_manifest.json',official/'statistics.json',official/'cluster_bootstrap_draws.csv',official/'output_manifest.json',SOURCE,Path(__file__)]
    record={'status':'PASS','n':49,'raw_audit_unchanged':True,'independent_math_recomputed_from_verified_raw_rows':True,'comparison':comparison,'input_hashes':{p.relative_to(BASE).as_posix():audit.sha(p) for p in inputs},'generation_calls':0,'GPT_API_calls':0,'Java_Maven_calls':0}
    p=out/'report.json';p.write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8');audit.log('INDEPENDENT_RAW49_LATE_COMPARISON',path=str(p),sha256=audit.sha(p),n=49,all20000_draws_match=True)
    print(json.dumps({'status':'PASS','n':49,'all20000_draws_match':True,'raw_artifacts_not_reread_or_modified':True}))
if __name__=='__main__':main()
