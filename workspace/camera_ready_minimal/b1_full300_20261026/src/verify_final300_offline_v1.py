"""Independent, read-only table/statistics verification. Never launches experiments.
Usage: python -B verify_final300_offline_v1.py --directory PATH --receipt NEW.json
"""
import argparse,csv,hashlib,json,math
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime,timezone
import numpy as np

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def close(a,b):
    assert np.allclose(a,b,atol=1e-9,rtol=1e-10), (a,b)
def independent_boot(rows,value):
    groups=defaultdict(list)
    for r in rows: groups[str(r['repo_id'])].append(float(value(r)))
    names=sorted(groups)
    sums=np.array([math.fsum(groups[k]) for k in names])
    counts=np.array([len(groups[k]) for k in names])
    rng=np.random.default_rng(20261023)
    simulated=[]
    # Explicit multiplicities, independent of the production vectorized reducer.
    for _ in range(20000):
        frequency=np.bincount(rng.integers(len(names),size=len(names)),minlength=len(names))
        simulated.append(float(np.dot(frequency,sums)/np.dot(frequency,counts)))
    return math.fsum(value(r) for r in rows)/len(rows),np.percentile(simulated,[2.5,97.5])

def main():
    p=argparse.ArgumentParser();p.add_argument('--directory',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);a=p.parse_args()
    assert not a.receipt.exists(), 'Never overwrite verification receipts'
    rows=load(a.directory/'class_results300.json');s=load(a.directory/'statistics.json')
    with (a.directory/'class_results300.csv').open(encoding='utf-8-sig',newline='') as f: flat=list(csv.DictReader(f))
    assert len(rows)==len(flat)==len({r['class_key'] for r in rows})==300
    assert sorted(r['index'] for r in rows)==list(range(1,301))
    verified_pins={}
    def pin(ref):
        if ref and ref.get('path') and ref.get('sha256'):
            path=ref['path'];expected=ref['sha256']
            if path not in verified_pins: verified_pins[path]=sha(path)
            assert verified_pins[path]==expected, path
    numeric=['observed_mutation_percent','end_to_end_score_percent','process_gate','G0_strict','E0_strict','G0_build','E0_build']
    for r,q in zip(rows,flat):
        assert r['class_key']==q['class_key'] and r['index']==int(q['index'])
        for k in numeric:
            if r[k] is None: assert q[k]==''
            else: close(float(q[k]),r[k])
        pin(r['selected_result']);pin(r['G0_historical_log']);pin(r['E0_historical_log'])
        for ref in r['raw_reports']: pin(ref)
        if r['observed_mutation_percent'] is not None:
            assert r['PIT_process_complete'] and r['focal_mutants']>0
            assert sum(r['PIT_status_counts'].values())==r['focal_mutants']
            close(r['observed_mutation_percent'],round(100*r['PIT_status_counts'].get('KILLED',0)/r['focal_mutants'],2))
        if r['policy_zero_without_observed_score']:
            assert r['observed_mutation_percent'] is None and r['end_to_end_score_percent']==0
    assert dict(Counter(r['score_basis'] for r in rows))==s['score_basis_counts']
    known=[r for r in rows if r['end_to_end_score_percent'] is not None]
    fixed=[r for r in rows if r['fixed49']]
    observed=[r for r in rows if r['observed_mutation_percent'] is not None]
    cohorts={
      'historical_G0_E0_all300':(rows,'E0_strict'),
      'historical_G0_E0_fixed49':(fixed,'E0_strict'),
      'G0_E1_fixed49_same_membership':(fixed,'end_to_end_score_percent'),
      'G0_E1_evidence_aware_end_to_end_available':(known,'end_to_end_score_percent'),
      'new_common_process_success_diagnostic_only':([r for r in known if r['G0_build']==r['process_gate']==1],'end_to_end_score_percent')}
    checked=[]
    for name,(subset,field) in cohorts.items():
        for arm,fun in [('left',lambda r:r['G0_strict']),('right',lambda r:r[field]),('left_minus_right',lambda r:r['G0_strict']-r[field])]:
            mean,ci=independent_boot(subset,fun);expected=s['cohorts'][name][arm]
            close(mean,expected['mean']);close(ci,expected['CI95_repository_percentile'])
            assert expected['n']==len(subset)
            checked.append(name+'/'+arm)
    mean,ci=independent_boot(observed,lambda r:r['observed_mutation_percent'])
    close(mean,s['cohorts']['E1_observed_PIT_only']['mean']);close(ci,s['cohorts']['E1_observed_PIT_only']['CI95_repository_percentile'])
    gknown=[r for r in rows if r['process_gate'] is not None]
    mean,ci=independent_boot(gknown,lambda r:100*r['process_gate'])
    g=s['gates']['E1_evidence_aware_process'];close(mean,g['available_rate_percent']['mean']);close(ci,g['available_rate_percent']['CI95_repository_percentile'])
    assert (g['pass'],g['fail'],g['unknown'])==(222,58,20)
    total=math.fsum(r['end_to_end_score_percent'] for r in known);unknown=300-len(known)
    limits=[total/300,(total+100*unknown)/300]
    close(limits,s['full300_partial_identification']['E1_mean_bounds'])
    gm=math.fsum(r['G0_strict'] for r in rows)/300
    close([gm-limits[1],gm-limits[0]],s['full300_partial_identification']['G0_minus_E1_mean_bounds'])
    r=next(r for r in rows if r['index']==294)
    assert r['PIT_status_counts']=={'NO_COVERAGE':38,'TIMED_OUT':6} and r['observed_mutation_percent']==0 and r['process_gate']==1
    assert len(known)==279 and len(observed)==221 and unknown==21
    result={'status':'PASS','at_utc':datetime.now(timezone.utc).isoformat(),'table_sha256':sha(a.directory/'class_results300.json'),'csv_sha256':sha(a.directory/'class_results300.csv'),'statistics_sha256':sha(a.directory/'statistics.json'),'rows':300,'unique_keys':300,'csv_nulls_preserved':True,'verified_unique_input_pins':len(verified_pins),'independent_bootstrap_checks':checked+['E1_observed_PIT_only','E1_process_gate'],'bootstrap_seed':20261023,'resamples':20000,'full300_complete':False,'new_experiments':0}
    with a.receipt.open('x',encoding='utf-8') as f: json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
