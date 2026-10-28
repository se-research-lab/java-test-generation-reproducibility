"""Independent decimal/CSV checks and bootstrap reconstruction from actual class rows."""
import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from statistics import mean, median

import numpy as np

BASE=Path(__file__).resolve().parents[1]
OUT=BASE/'outputs'


def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))


def check_close(actual,expected):
    assert abs(float(actual)-float(expected))<1e-10,(actual,expected)


def main():
    source=rows(BASE/'backup/original/scripts_v2/results/runs/full300_merged_20260724_paper/metrics_wide.csv')
    chosen=[r for r in source if r['gpt_compilation']=='1' and r['evosuite_compilation']=='1']
    data=rows(OUT/'paired49.csv')
    assert sorted(r['class_key'] for r in chosen)==sorted(r['class_key'] for r in data)
    assert len(chosen)==49
    g=[Decimal(r['gpt_mutation_coverage']) for r in chosen]
    e=[Decimal(r['evosuite_mutation_coverage']) for r in chosen]
    diff=[a-b for a,b in zip(g,e)]
    stat=json.loads((OUT/'statistics.json').read_text(encoding='utf-8'))
    for key,value in [('gpt_mean',mean(g)),('evo_mean',mean(e)),('gpt_median',median(g)),
                      ('evo_median',median(e)),('paired_mean_difference_pp',mean(diff)),
                      ('paired_median_difference_pp',median(diff))]:check_close(stat[key],value)
    assert [sum(d>0 for d in diff),sum(d<0 for d in diff),sum(d==0 for d in diff)]==[39,4,6]
    byrepo={}
    for r,d in zip(chosen,diff):byrepo.setdefault(r['repo_id'],[]).append(float(d))
    labels=sorted(byrepo)  # Canonical lexicographic string labels, explicit and reproducible.
    draws=np.random.default_rng(20261023).integers(0,len(labels),(20000,len(labels)))
    independent=[]
    for sample in draws:
        actual_classes=[d for index in sample for d in byrepo[labels[index]]]
        independent.append(sum(actual_classes)/len(actual_classes))
    exported=rows(OUT/'cluster_bootstrap_draws.csv')
    assert len(exported)==20000
    assert np.allclose(independent,[float(r['class_weighted_difference_pp']) for r in exported],atol=1e-10,rtol=0)
    bounds=np.quantile(independent,[.025,.975])
    assert np.allclose(bounds,stat['cluster_percentile_95ci_mean_difference_pp'],atol=1e-10,rtol=0)
    manifest=json.loads((OUT/'output_manifest.json').read_text(encoding='utf-8'))
    for name,expected in manifest.items():assert hashlib.sha256((OUT/name).read_bytes()).hexdigest()==expected
    evidence=rows(OUT/'paired49_artifact_provenance.csv')
    assert len(evidence)==98
    assert {(r['class_key'],r['arm']) for r in evidence}=={(r['class_key'],a) for r in chosen for a in ['gpt','evosuite']}
    for r in evidence:
        assert hashlib.sha256((BASE/'backup/original'/r['backup_relative']).read_bytes()).hexdigest()==r['sha256']
    report={'status':'PASS','independent_arithmetic':'Python Decimal and statistics',
            'pair_keys_checked':49,'repository_count':len(labels),'artifact_files_verified':98,
            'bootstrap_validation':'all 20000 draws independently reconstructed from individual class rows',
            'cluster_order':labels,'output_hashes_verified':len(manifest),
            'rq123_checked_by_separate_guard':True,
            'generation_and_java_measurement_jobs':0,
            'limits':'No raw XML/PIT audit; no claim that assertions-disabled E0 is a standard oracle baseline'}
    dest=BASE/'validation/independent_checks.json'
    with dest.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
