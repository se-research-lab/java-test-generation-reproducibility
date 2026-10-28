"""Independent exact-count and bootstrap-draw reconstruction for new analytics."""
import csv,json,sys
from decimal import Decimal
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
source=BASE/'backup/original/scripts_v2/results/runs/full300_merged_20260724_paper/metrics_wide.csv'
with source.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
m=json.loads((BASE/'outputs/maven260_sensitivity/summary.json').read_text())
for s in m['table']:
    selected=rows if s['population']=='all300' else [r for r in rows if r['build_tool']==('Maven' if s['population']=='Maven260' else 'Gradle')]
    assert len(selected)==s['n']
    for label,key in [('GPT_builds','gpt_compilation'),('E0_builds','evosuite_compilation')]:assert sum(int(r[key]) for r in selected)==s[label]
    assert sum(s[k] for k in ['both_build','GPT_only','E0_only','neither_build'])==s['n']
c=json.loads((BASE/'outputs/cluster300_sensitivity/summary.json').read_text())
repos=sorted({r['repo_id'] for r in rows});assert repos==c['repo_order']
mutation={repo:sum(Decimal(r['gpt_strict_mutation_coverage'])-Decimal(r['evosuite_strict_mutation_coverage']) for r in rows if r['repo_id']==repo) for repo in repos}
build={repo:sum(int(r['gpt_compilation'])-int(r['evosuite_compilation']) for r in rows if r['repo_id']==repo) for repo in repos}
n=0
with (BASE/'outputs/cluster300_sensitivity/bootstrap_draws.csv').open(newline='') as f:
    for r in csv.DictReader(f):
        selected=[repos[int(i)] for i in r['repo_indices_zero_based'].split(';')];assert len(selected)==30
        expected=sum(mutation[x] for x in selected)/Decimal(300)
        assert abs(expected-Decimal(r['strict_mutation_mean_difference_pp']))<Decimal('0.0000000001')
        assert abs(Decimal(sum(build[x] for x in selected))/3-Decimal(r['build_rate_difference_pp']))<Decimal('0.0000000001')
        n+=1
assert n==20000
report={'status':'PASS','Maven260_and_Gradle40_counts':'exact','cluster300_draws_reconstructed_independently':n,'arithmetic':'Decimal for per-repository sums and mean differences','originals_unchanged':audit.sha(source)==audit.sha(audit.RUN/'metrics_wide.csv')}
p=BASE/'validation/new_analytics_independent.json'
with p.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
print(json.dumps(report,indent=2))
