"""Repository-level descriptive sensitivity on the frozen full300 data."""
import csv,json,sys
from pathlib import Path
import numpy as np
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
out=BASE/'outputs/cluster300_sensitivity';out.mkdir(exist_ok=False)
protocol={'scope':'post-review sensitivity; historical outcomes already known','replicates':20000,'seed':20261023,
 'estimands':['class-weighted strict mutation mean GPT minus E0 in pp','paired process-build rate difference GPT minus E0 in pp'],
 'resampling':'sample whole repository clusters with replacement, preserve pairs; lexicographic repo order; ratio of total difference to total class count',
 'confidence':'95% percentile CI','new_NI_decision':False,'new_generation':False,'replaces_RQ123_inputs':False}
with (out/'protocol.json').open('x',encoding='utf-8') as f:json.dump(protocol,f,indent=2)
p=BASE/'backup/original/scripts_v2/results/runs/full300_merged_20260724_paper/metrics_wide.csv'
with p.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
assert len(rows)==300 and audit.sha(p)==audit.sha(audit.RUN/'metrics_wide.csv')
repos=sorted({r['repo_id'] for r in rows});counts=[];mutation=[];build=[];table=[]
for repo in repos:
    sub=[r for r in rows if r['repo_id']==repo]
    ms=sum(float(r['gpt_strict_mutation_coverage'])-float(r['evosuite_strict_mutation_coverage']) for r in sub)
    bs=sum(int(r['gpt_compilation'])-int(r['evosuite_compilation']) for r in sub)
    counts.append(len(sub));mutation.append(ms);build.append(bs)
    table.append({'repo_id':repo,'n':len(sub),'strict_mutation_mean_difference_pp':ms/len(sub),'process_build_difference_pp':100*bs/len(sub)})
assert len(repos)==30 and counts==[10]*30
counts=np.array(counts);mutation=np.array(mutation);build=np.array(build)
rng=np.random.default_rng(20261023);draws=rng.integers(0,len(repos),size=(20000,len(repos)))
md=mutation[draws].sum(axis=1)/counts[draws].sum(axis=1);bd=100*build[draws].sum(axis=1)/counts[draws].sum(axis=1)
with (out/'bootstrap_draws.csv').open('x',encoding='utf-8',newline='') as f:
    w=csv.writer(f);w.writerow(['draw','repo_indices_zero_based','strict_mutation_mean_difference_pp','build_rate_difference_pp'])
    for i,(d,m,b) in enumerate(zip(draws,md,bd),1):w.writerow([i,';'.join(map(str,d)),repr(float(m)),repr(float(b))])
with (out/'repository_table.csv').open('x',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
report={'n':300,'repository_n':30,'repo_order':repos,'source_sha256':audit.sha(p),
 'strict_mutation_mean_difference_pp':float(mutation.sum()/300),
 'strict_mutation_repository_percentile95CI_pp':np.quantile(md,[.025,.975]).tolist(),
 'build_rate_difference_pp':float(100*build.sum()/300),
 'build_rate_repository_percentile95CI_pp':np.quantile(bd,[.025,.975]).tolist(),
 'strict_mean_leave_one_repo_out_range_pp':[float(min((mutation.sum()-x)/(300-10) for x in mutation)),float(max((mutation.sum()-x)/(300-10) for x in mutation))],
 'direction_counts':{'GPT_higher':sum(float(r['gpt_strict_mutation_coverage'])>float(r['evosuite_strict_mutation_coverage']) for r in rows),'E0_higher':sum(float(r['gpt_strict_mutation_coverage'])<float(r['evosuite_strict_mutation_coverage']) for r in rows),'ties':sum(float(r['gpt_strict_mutation_coverage'])==float(r['evosuite_strict_mutation_coverage']) for r in rows)},
 'limitations':['historical E0 assertions-off','repository bootstrap sensitivity does not validate legacy measurement gate','mean CI is not the paper signed-rank NI test and does not close NI-margin justification','fixed300/GPT RQ123 inputs untouched']}
with (out/'summary.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
ci=report['strict_mutation_repository_percentile95CI_pp'];bc=report['build_rate_repository_percentile95CI_pp']
text=f'''# Clustering sensitivity trên full300

Dữ liệu G0/E0 lịch sử; E0 tắt assertions. Resample nguyên30 repository, giữ cặp và10 class trong mỗi repo;20.000 draws, seed20261023. Đây là phân tích bổ sung sau review, không phải repeated generation.

- Mean strict-mutation difference GPT−E0: {report['strict_mutation_mean_difference_pp']:.2f}pp; repository-bootstrap95%CI [{ci[0]:.2f};{ci[1]:.2f}]pp.
- Paired process-build rate difference GPT−E0: {report['build_rate_difference_pp']:.2f}pp; repository-bootstrap95%CI [{bc[0]:.2f};{bc[1]:.2f}]pp.
- Direction counts giữ nguyên46/70/184; mean/rank divergence vẫn cần nêu trong abstract theo R2.4.

CI này thuộc mean difference. Không thay thế trực tiếp signed-rank NI test của paper, không xác nhận margin5pp và không đủ để kết luận về EvoSuite bật assertions. Dữ liệu GPT của RQ1–RQ3 không đổi. Các draws và thứ tự repository được xuất để kiểm tra độc lập.
'''
(out/'BAO_CAO_CLUSTER300.md').write_text(text,encoding='utf-8')
with (out/'completion_record.json').open('x',encoding='utf-8') as f:json.dump({'summary_sha256':audit.sha(out/'summary.json'),'protocol_sha256':audit.sha(out/'protocol.json'),'new_generation':False},f,indent=2)
print(json.dumps(report,indent=2))
