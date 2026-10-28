"""Read-only paper/evidence audit; only writes into a new audit folder. No experiments."""
from pathlib import Path
from collections import Counter
import csv, hashlib, json, zipfile, math
import numpy as np
from scipy.stats import wilcoxon, rankdata, binomtest, norm
import scipy, fitz

ROOT=Path('D:/A_ThucNghiem');R=ROOT/'camera_ready_minimal/b1_full300_20261026'
O=R/'paper_reaudit_20261028_v1';F=R/'completion_amendment_v1/final300_offline_v1'
D=R/'camera_ready_checkpoint300_v1/delivery'
H=ROOT/'scripts_v2/results/runs/full300_merged_20260724_paper'
def load(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def read(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def num(x):return float(x) if x!='' else None
rows=load(F/'class_results300.json');stats=load(F/'statistics.json');wide=read(H/'metrics_wide.csv');long=read(H/'metrics_long.csv')
by={r['class_key']:r for r in rows}; wby={r['class_key']:r for r in wide}
assert len(rows)==len(wide)==len(by)==len(wby)==300 and len(long)==600 and set(by)==set(wby)
checks=[]
def eq(label,actual,expected):
    ok=bool(np.allclose(actual,expected,atol=1e-9,rtol=1e-9))
    checks.append(dict(label=label,actual=actual,expected=expected,ok=ok))
    assert ok,(label,actual,expected)
for r in rows:
    w=wby[r['class_key']]
    for a,b in [('G0','gpt'),('E0','evosuite')]:
        assert r[a+'_strict']==float(w[b+'_strict_mutation_coverage'])
        assert r[a+'_build']==int(w[b+'_compilation'])
    assert r['fixed49']==(int(w['gpt_compilation'])==int(w['evosuite_compilation'])==1)

table3=[]
for arm in ['gpt','evosuite']:
    for metric in ['branch','line','method','mutation']:
        key=arm+'_'+metric+'_coverage'
        v=[float(w[key]) for w in wide if int(w[arm+'_compilation'])==1 and w[key]!='']
        strict=[float(w[arm+'_strict_'+metric+'_coverage']) for w in wide]
        table3.append(dict(arm=arm,metric=metric,n=len(v),mean=float(np.mean(v)),median=float(np.median(v)),strict_mean=float(np.mean(strict)),strict_median=float(np.median(strict))))
for arm in ['gpt','evosuite']:
    l={x['class_key']:x for x in long if x['arm']==arm}
    for w in wide:
        for metric in ['compilation','branch_coverage','line_coverage','method_coverage','mutation_coverage','strict_mutation_coverage']:
            assert num(w[arm+'_'+metric])==num(l[w['class_key']][metric])

def wrank(v):
    a=np.array(v);a=a[a!=0];r=rankdata(abs(a));wp=float(r[a>0].sum());wm=float(r[a<0].sum())
    return dict(n=len(a),Wplus=wp,rank_biserial=(wp-wm)/(wp+wm),p_greater=float(wilcoxon(a,alternative='greater').pvalue))
g=[float(w['gpt_mutation_coverage']) for w in wide if w['gpt_compilation']=='1']
branch=[float(w['gpt_branch_coverage']) for w in wide if w['gpt_compilation']=='1' and w['gpt_branch_coverage']!='']
delta=np.array([r['G0_strict']-r['E0_strict'] for r in rows])
rq1=wrank(np.array(g)-44.5);rq2=wrank(np.array(branch)-41.9);rq4=wrank(delta+5)
rq3p=float(binomtest(61,300,.286,alternative='greater').pvalue)
rq5p=float(binomtest(12,121,.5,alternative='two-sided').pvalue)
p=[rq1['p_greater'],rq3p,rq4['p_greater'],rq5p];order=np.argsort(p);holm=[0.]*4;floor=0.
for i,k in enumerate(order):floor=max(floor,min(1.,(4-i)*p[k]));holm[k]=floor
eq('RQ1 W+',rq1['Wplus'],1334);eq('RQ2 W+',rq2['Wplus'],955)
z=norm.ppf(.975);phat=61/300;den=1+z*z/300
center=(phat+z*z/600)/den;radius=z*math.sqrt(phat*(1-phat)/300+z*z/(4*300**2))/den
wilson=[100*(center-radius),100*(center+radius)]
historical_rqs={'RQ1':rq1,'RQ2_descriptive_no_p_decision':{k:v for k,v in rq2.items() if k!='p_greater'},'RQ3':{'p_greater':rq3p,'Wilson_percent':wilson},'RQ4':rq4,'RQ5':{'p_two_sided':rq5p,'OR_G0_over_E0':12/109},'Holm_RQ1_RQ3_RQ4_RQ5':holm,'scipy_version':scipy.__version__}

def boot(subset,fn):
    ids=sorted({str(r['repo_id']) for r in subset});sums=np.array([math.fsum(fn(r) for r in subset if str(r['repo_id'])==k) for k in ids]);counts=np.array([sum(str(r['repo_id'])==k for r in subset) for k in ids])
    ix=np.random.default_rng(20261023).integers(0,len(ids),(20000,len(ids)));b=sums[ix].sum(1)/counts[ix].sum(1)
    return np.percentile(b,[2.5,97.5]).tolist()
for build in ['maven','gradle']:
    subset=[r for r in rows if r['build_tool']==build and r['end_to_end_score_percent'] is not None]
    eq(build+' E1 gap CI',boot(subset,lambda r:r['G0_strict']-r['end_to_end_score_percent']),stats['strata'][build]['E1_available']['left_minus_right']['CI95_repository_percentile'])
known=[r for r in rows if r['end_to_end_score_percent'] is not None]
old3=load(R/'jobs/003/result.json')
eq('Class3 original sensitivity CI',boot(known,lambda r:r['G0_strict']-(old3['legacy_strict_mutation_percent'] if r['index']==3 else r['end_to_end_score_percent'])),stats['sensitivities']['original_class3_result']['left_minus_right']['CI95_repository_percentile'])
eq('E0 build difference repository CI',boot(rows,lambda r:100*(r['G0_build']-r['E0_build'])),[-47,-17.666666666666668])
bound_checks={}
for name,predicate in [('base',lambda r:r['end_to_end_score_percent'] is None),('timeouts',lambda r:r['end_to_end_score_percent'] is None or r['index'] in [112,269]),('nonpassing',lambda r:r['end_to_end_score_percent'] is None or r['nonpassing_suite_with_valid_PIT'])]:
    missing=[r for r in rows if predicate(r)];s=math.fsum(r['end_to_end_score_percent'] for r in rows if not predicate(r));gm=math.fsum(r['G0_strict'] for r in rows)/300
    bound_checks[name]={'unknown':len(missing),'E1_mean':[s/300,(s+100*len(missing))/300],'G0_minus_E1':[gm-(s+100*len(missing))/300,gm-s/300]}
eq('timeout bounds',bound_checks['timeouts']['G0_minus_E1'],stats['sensitivities']['hold112_269_timeout_as_unknown_instead_of_policy_zero']['G0_minus_E1_mean_bounds'])
eq('nonpassing bounds',bound_checks['nonpassing']['G0_minus_E1'],stats['sensitivities']['hold_nonpassing_native_suite_unresolved_bounds']['G0_minus_E1_mean_bounds'])

raw_details=[]
for r in rows:
    if r['observed_mutation_percent'] is None:continue
    ref=r['raw_reports'][0];assert sha(ref['path'])==ref['sha256']
    with Path(ref['path']).open(encoding='utf-8-sig',newline='') as f:raw=list(csv.reader(f))
    focal=[x for x in raw if x[0].casefold()==r['class_key'].split('/')[-1] and x[1].rpartition('.')[0]==r['selected_test_fqcn'].rpartition('.')[0]]
    c=Counter(x[5] for x in focal);value=round(100*c['KILLED']/len(focal),2)
    assert value==r['observed_mutation_percent'] and dict(c)==r['PIT_status_counts']
    raw_details.append(dict(index=r['index'],K=c['KILLED'],N=len(focal),TIMED_OUT=c['TIMED_OUT'],score=value))
historical=load(R/'completion_amendment_v1/analysis300_checkpoint_v2/historical_report_formula_audit300.json')
graw=[]
for h in historical:
    if h['owner']!='G0':continue
    r=by[h['class_key']];ref=h['report_candidates'][0];assert sha(ref['path'])==ref['sha256']
    with Path(ref['path']).open(encoding='utf-8-sig',newline='') as f:raw=list(csv.reader(f))
    focal=[x for x in raw if x[0].casefold()==r['class_key'].split('/')[-1] and x[1].rpartition('.')[0]==r['selected_test_fqcn'].rpartition('.')[0]]
    c=Counter(x[5] for x in focal)
    assert dict(c)==h['focal_status_counts'] and round(100*c['KILLED']/len(focal),2)==r['G0_strict']
    graw.append(h['index'])
assert len(raw_details)==221 and len(graw)==61

stage={k:dict(Counter(r[k] for r in rows)) for k in ['generation','compile_production_evidence','compile_test_evidence','test_execution','PIT','score_basis','process_gate']}
for k in ['generation','compile_production_evidence','compile_test_evidence','test_execution','PIT']:assert stage[k]==stats['stage_counts'][k]
gates={}
for arm in ['E0_build','process_gate']:
    subset=[r for r in rows if r[arm] is not None]
    gates[arm]={str(a)+str(b):sum(r['G0_build']==a and r[arm]==b for r in subset) for a in [0,1] for b in [0,1]}
fixed=[r for r in rows if r['fixed49']]
fixed_flags=[{k:r[k] for k in ['index','class_key','suite_evidence_complete','test_execution','observed_mutation_percent']} for r in fixed if not r['suite_evidence_complete']]
sample={'n':len(wide),'repos':len({w['repo_id'] for w in wide}),'repo_quotas':dict(Counter(Counter(w['repo_id'] for w in wide).values())),'build_tool':dict(Counter(w['build_tool'] for w in wide)),'complexity':dict(Counter(w['complexity_half'] for w in wide)),'nloc_quartiles':np.percentile([float(w['nloc']) for w in wide],[25,50,75]).tolist(),'method_median':float(np.median([float(w['method_count']) for w in wide])),'cc_min_median_max':np.percentile([float(w['max_method_cc']) for w in wide],[0,50,100]).tolist()}
pdf=D/'FISAT2026_camera_ready.pdf';pd=fitz.open(pdf)
page_text=[];fontcheck=[];bbox_bad=[]
for i,p in enumerate(pd):
    page_text.append(f'PAGE {i+1}\n'+p.get_text())
    for w in p.get_text('words'):
        if not (0<=w[0]<=w[2]<=p.rect.width+.1 and 0<=w[1]<=w[3]<=p.rect.height+.1):bbox_bad.append([i+1,w])
    for f in p.get_fonts():assert pd.extract_font(f[0])[3];fontcheck.append(f[3])
    folder=O/'render';folder.mkdir(exist_ok=True)
    p.get_pixmap(matrix=fitz.Matrix(1.4,1.4),alpha=False).save(folder/f'page-{i+1:02d}.png')
assert len(pd)==15 and not bbox_bad
with zipfile.ZipFile(D/'FISAT2026_camera_ready_source.zip') as z:
    assert z.testzip() is None and hashlib.sha256(z.read(pdf.name)).hexdigest()==sha(pdf)
delivery_hashes=[]
for line in (D/'SHA256SUMS.txt').read_text().splitlines():
    h,n=line.split('  ',1);assert sha(D/n)==h;delivery_hashes.append(n)
(O/'paper_extracted.txt').write_text('\n\n'.join(page_text),encoding='utf-8')
result=dict(status='PASS_NUMERIC_RECOMPUTATION',pdf_sha256=sha(pdf),rows=300,historical_rows=600,keys_join_exact=True,table3=table3,historical_rqs=historical_rqs,extra_CI_and_bounds_checks=checks,bounds=bound_checks,stage_counts=stage,paired_gates=gates,fixed49_uncertified_suite_indices=fixed_flags,sample=sample,E1_raw_reports_recounted=len(raw_details),G0_raw_reports_recounted=len(graw),E0_raw_reports_independently_attributed=0,class294=next(x for x in raw_details if x['index']==294),pages=15,embedded_fonts=len(set(fontcheck)),source_zip_same_pdf=True,delivery_hashes_rechecked=len(delivery_hashes),no_new_experiments=True,limitations=['Native gate is not all-test pass','E0 raw ownership incomplete','Historical class bootstrap CIs need archived recipe check','Numerical match does not validate causal tool ranking'])
(O/'NUMERIC_REAUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
with (O/'TABLE3_RECOMPUTED.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(table3[0]));w.writeheader();w.writerows(table3)
print(json.dumps(result,ensure_ascii=False,indent=2))
