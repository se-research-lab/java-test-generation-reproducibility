"""Post-review fixed49 E1 analysis; refuses partial/changed inputs, never runs Java/GPT.
The legacy scoring rule is preserved. Raw flags describe validity, not new scales.
"""
import argparse,csv,hashlib,importlib.util,json,re,statistics,sys
from collections import Counter
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET
import numpy as np
BASE=Path(__file__).resolve().parents[1];STAGE=BASE/'e49_driver'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def csvread(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def rawcsv(p):
    if not p.is_file():return []
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.reader(f))
def dec(x):return Decimal(str(x))
def write_json(p,obj):
    with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
def write_csv(p,rows):
    assert rows
    fields=list(dict.fromkeys(k for r in rows for k in r))
    with p.open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def counter_hash(rows):
    # Keep duplicates: CSV lacks bytecode index, so this is a multiset fingerprint,
    # not a complete PIT mutation identifier or proof of historical arm identity.
    data=sorted([list(r[:5]) for r in rows])
    return hashlib.sha256(json.dumps(data,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def focal(rows,j):
    return [r for r in rows if r[0].replace('.java','')==j['focal_class'] and (r[1].rsplit('.',1)[0] if '.' in r[1] else '')==j['package']]
def class_hashes(module,j):
    root=module/'target/classes'/Path(*j['package'].split('.'));result={}
    if root.is_dir():
        for p in root.glob(j['focal_class']+'*.class'):
            if p.is_file() and (p.stem==j['focal_class'] or p.stem.startswith(j['focal_class']+'$')):result[p.name]=sha(p)
    return result

def validate_inputs(archive):
    jobs=read(STAGE/'input_manifest49.json');frozen=csvread(BASE/'outputs/paired49.csv')
    paths=[STAGE/('job_result_%02d.json'%i) for i in range(1,50)]
    missing=[p.name for p in paths if not p.exists()]
    assert not missing,'Incomplete49: missing '+','.join(missing)
    assert (STAGE/'results49.json').exists(),'No final results49.json; do not analyse partial cohort'
    results=[read(p) for p in paths]
    assert len(jobs)==len(frozen)==len(results)==49
    keys=[j['class_key'] for j in jobs]
    assert len(set(keys))==49 and keys==[r['class_key'] for r in frozen]==[r['class_key'] for r in results]
    assert read(STAGE/'results49.json')==results,'Final batch/index summaries differ'
    assert {j['repo_id'] for j in jobs}=={r['repo_id'] for r in frozen} and len({j['repo_id'] for j in jobs})==15
    assert read(archive/'summary.json')['all49_complete'],'Raw observer not complete'
    lock=read(STAGE/'readiness_lock.json')
    for p,h in lock['code_and_input_hashes'].items():assert sha(BASE/p)==h,'Locked source/input changed: '+p
    for p,h in {**lock['tool_hashes'],**lock['context_source_hashes']}.items():assert sha(p)==h,'Locked tool/context changed: '+p
    for rel,source in [('resume_guard01','resume_e49_after_filename_guard.py'),('resume_guard02','resume_e49_after_process_interruption.py')]:
        admission=read(STAGE/rel/'admission.json')
        assert admission['source_sha256']==sha(BASE/'src'/source)
        assert admission['same_protocol_sha256']==sha(STAGE/'protocol49.json')
        assert admission['same_readiness_lock_sha256']==sha(STAGE/'readiness_lock.json')
        for path,h in admission['retained_prefix_file_hashes'].items():assert sha(BASE/path)==h,'Retained result/log changed'
    # Read-only original GPT cohort/artifact guard; no experiment module/API import.
    guard=BASE.parents[1]/'review_reports/minimal_camera_ready_20261023/guard_rq123_frozen.py'
    spec=importlib.util.spec_from_file_location('gpt_guard_analysis',guard);g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
    assert g.collect()==read(g.LOCK),'Frozen GPT observations/artifacts changed'
    return jobs,frozen,results

def inspect_job(j,g,row,archive):
    i=j['job_index'];work=STAGE/'jobs'/('%02d'%i);module=work/'repo'/j['module'];test=j['selected_test_fqcn']
    assert row['job_index']==i and row['repo_id']==j['repo_id'] and row['GPT_API_calls']==0
    assert dec(row['G0_archived_mutation_percent'])==dec(g['gpt_mutation_coverage'])==dec(j['gpt_archived_mutation_percent'])
    assert dec(row['E0_archived_mutation_percent'])==dec(g['evosuite_mutation_coverage'])==dec(j['e0_archived_mutation_percent'])
    focal_source=work/'repo'/j['focal_path'];focal_source_available=focal_source.is_file()
    if focal_source_available:assert sha(focal_source)==j['focal_sha256'],'Existing focal bytes changed'
    else:assert 'error_type' in row,'Focal missing without an explicit technical-failure row'
    if 'seed' in row:assert row['seed']==j['seed']==20261023+j['sample_index']
    manifest=read(archive/('%02d'%i)/'manifest.json')
    assert manifest['class_key']==j['class_key'] and manifest['result_sha256']==sha(STAGE/('job_result_%02d.json'%i))
    copies=manifest.get('raw_artifact_copies',manifest.get('files',[]))
    for r in copies:assert sha(BASE/r['source'])==r['sha256']==sha(BASE/r['copy']),'Raw archive bytes changed'
    after=read(work/'pom_after_manifest.json') if (work/'pom_after_manifest.json').exists() else {}
    for path,h in after.items():assert sha(work/path)==h,'Saved post-integration POM changed'
    generated=read(work/'generated_manifest.json') if (work/'generated_manifest.json').exists() else {}
    for path,h in generated.items():assert sha(work/path)==h,'Generated/observed test bytes changed'
    # Windows broad glob also logged some unchanged human files; do not call them generated.
    native=[p for p in generated if Path(p).name.endswith(('_ESTest.java','_ESTest_scaffolding.java'))]
    extra=[p for p in generated if p not in native]
    commands=[read(p) for p in sorted(work.glob('command_*.json'))]
    gens=[r for r in commands if '-jar' in r['argv']]
    for c in commands:
        for label in ['stdout','stderr']:assert sha(BASE/c[label])==c[label+'_sha256']
        argv=c['argv']
        if '-Dtest='+test in argv:continue
        if any(x.startswith('-Dtest=') for x in argv):raise AssertionError('Foreign -Dtest selector')
    for c in gens:
        argv=c['argv'];expected=['-Dassertions=true','-Dtest_scaffolding=true','-Dno_runtime_dependency=false','-Dassertion_strategy=MUTATION','-Dcriterion=BRANCH','-Dsearch_budget=60','-Dtest_archive=false','-Duse_separate_classloader=false']
        assert all(x in argv for x in expected),'Profile differs on actual argv'
        assert int(argv[argv.index('-seed')+1])==j['seed'] and c['timeout'] in [True,False]
    assert len(gens)<=2
    if 'generation_attempts' in row:assert row['generation_attempts']==len(gens)
    suites=[];errors=[]
    for path in sorted((module/'target/surefire-reports').glob('TEST-*.xml')):
        root=ET.parse(path).getroot();s={'name':root.get('name'),**{k:int(root.get(k,'0')) for k in ['tests','failures','errors','skipped']}};suites.append(s)
        for kind in ['failure','error']:
            for e in root.findall('.//'+kind):errors.append({'kind':kind,'type':e.get('type'),'message':e.get('message')})
    only=bool(suites) and all(s['name']==test for s in suites)
    passing=bool(suites) and only and sum(s['tests'] for s in suites)>0 and all(s['failures']+s['errors']==0 for s in suites)
    skipped=sum(s['skipped'] for s in suites);executed=sum(s['tests']-s['skipped'] for s in suites)
    if suites:assert only,'Foreign Surefire suite executed'
    rows=rawcsv(module/'target/pit-reports/mutations.csv');assert all(len(r)==7 for r in rows)
    foc=focal(rows,j);killed=sum(r[5]=='KILLED' for r in foc)
    foreign_kills=[r for r in rows if r[5]=='KILLED' and test not in r[6]]
    assert not foreign_kills,'PIT kills attributed to foreign suite'
    jac=module/'target/site/jacoco/jacoco.csv'
    coverage=[r for r in csvread(jac) if r.get('CLASS')==j['focal_class'] and r.get('PACKAGE','').replace('/','.')==j['package']] if jac.exists() else []
    gate=int(row['legacy_process_build']);assert gate in [0,1]
    rawscore=round(100*killed/len(foc),2) if foc else None
    strict=rawscore if gate and rawscore is not None else 0.0
    if 'error_type' not in row:
        assert suites==row['surefire_suites'] and passing==row['suite_pass']
        assert len(foc)==row['focal_mutants'] and killed==row['killed_mutants']
        assert dec(strict)==dec(row['legacy_strict_mutation_percent'])
        assert row['measurement_evidence_complete']==bool(passing and foc and coverage)
        if rawscore is not None:assert dec(rawscore)==dec(row['mutation_score_percent'])
    else:assert dec(row['legacy_strict_mutation_percent'])==0 and gate==0
    # A runtime initialization error remains a pipeline outcome under legacy scoring.
    historical=Path(j['source_repo'])/j['module'];old=rawcsv(historical/'target/pit-reports/mutations.csv');oldf=focal(old,j) if old else []
    bh=class_hashes(module,j);oldbh=class_hashes(historical,j)
    diag={'job_index':i,'class_key':j['class_key'],'native_generated_files':native,'extra_unchanged_human_manifest_entries':extra,
        'surefire_suites':suites,'errors':errors,'PIT_module_status_counts':dict(Counter(r[5] for r in rows)),
        'PIT_focal_status_counts':dict(Counter(r[5] for r in foc)),'PIT_killing_suite_check':'PASS_no_foreign_kills',
        'focal_bytecode':bh,'remaining_historical_bytecode':oldbh,
        'bytecode_matches_remaining_snapshot':bool(bh and oldbh) and bh==oldbh,
        'focal_mutant_multiset_sha256':counter_hash(foc) if foc else None,
        'remaining_historical_multiset_sha256':counter_hash(oldf) if oldf else None,
        'mutant_multiset_matches_remaining_snapshot':bool(foc and oldf) and counter_hash(foc)==counter_hash(oldf),
        'history_limit':'remaining historical snapshot is not certified as both arms; cols0-4 multiset is not a complete mutant identifier',
        'archive_files_verified':len(copies),'generation_attempts':len(gens),
        'actual_command_wall_seconds':sum(c['duration_seconds'] for c in commands)}
    record={'job_index':i,'class_key':j['class_key'],'repo_id':j['repo_id'],'focal_class':j['focal_class'],
        'G0_archived_mutation_percent':str(dec(g['gpt_mutation_coverage'])),
        'E0_archived_mutation_percent':str(dec(g['evosuite_mutation_coverage'])),
        'E1_legacy_strict_mutation_percent':str(dec(row['legacy_strict_mutation_percent'])),
        'G0_minus_E1_pp':str(dec(g['gpt_mutation_coverage'])-dec(row['legacy_strict_mutation_percent'])),
        'E1_minus_E0_pp':str(dec(row['legacy_strict_mutation_percent'])-dec(g['evosuite_mutation_coverage'])),
        'legacy_process_build':gate,'suite_pass':passing,'skipped_tests':skipped,'non_skipped_surefire_cases':executed,
        'measurement_evidence_complete':row['measurement_evidence_complete'],'generation_success':row.get('generation_success',False),
        'focal_mutants':len(foc),'killed_mutants':killed,'PIT_report_present':(module/'target/pit-reports/mutations.csv').exists(),
        'JaCoCo_focal_present':bool(coverage),'focal_source_available':focal_source_available,'seed':j['seed'],'generation_attempts':len(gens),
        'TestRule_missing':any('TestRule' in str(e.get('message','')) for e in errors),
        'error_type':row.get('error_type',''),'technical_error':row.get('error',''),'error_message':'; '.join(([str(row['error'])] if row.get('error') else [])+[str(e.get('message','')) for e in errors])}
    return record,diag

def summarize(rows):
    g=[dec(r['G0_archived_mutation_percent']) for r in rows];e0=[dec(r['E0_archived_mutation_percent']) for r in rows];e1=[dec(r['E1_legacy_strict_mutation_percent']) for r in rows]
    def mean(v):return float(sum(v)/len(v))
    def dif(a,b):
        v=[x-y for x,y in zip(a,b)]
        return {'mean_pp':mean(v),'median_pp':float(statistics.median(v)),'G_higher':sum(x>0 for x in v),'E_higher':sum(x<0 for x in v),'ties':sum(x==0 for x in v)}
    result={'n':49,'repositories':15,'scope':'historical common-build fixed49; all Maven; no replacement/selection on E1 success',
        'G0_mean':mean(g),'G0_median':float(statistics.median(g)),'E0_mean':mean(e0),'E0_median':float(statistics.median(e0)),
        'E1_legacy_strict_mean':mean(e1),'E1_legacy_strict_median':float(statistics.median(e1)),
        'G0_minus_E0':dif(g,e0),'G0_minus_E1':dif(g,e1),'E1_minus_E0_mean_pp':mean([a-b for a,b in zip(e1,e0)]),
        'E1_counts':{k:sum(bool(r[k]) for r in rows) for k in ['legacy_process_build','suite_pass','measurement_evidence_complete','generation_success','PIT_report_present','JaCoCo_focal_present','TestRule_missing']},
        'E1_classes_with_skips':sum(r['skipped_tests']>0 for r in rows),'E1_classes_with_non_skipped_surefire_cases':sum(r['non_skipped_surefire_cases']>0 for r in rows),
        'GPT_API_calls':0,'new_NI_test':False,'historical_GPT_remeasured':False,'RQ123_membership_or_scores_updated':False}
    repos=sorted({r['repo_id'] for r in rows});sums=[];counts=[];repo_rows=[]
    for repo in repos:
        ix=[i for i,r in enumerate(rows) if r['repo_id']==repo];ds=[g[i]-e1[i] for i in ix];sums.append(float(sum(ds)));counts.append(len(ix))
        repo_rows.append({'repo_id':repo,'n':len(ix),'G0_minus_E1_mean_pp':mean(ds),'E1_suite_pass':sum(rows[i]['suite_pass'] for i in ix)})
    draw=np.random.default_rng(20261023).integers(0,len(repos),size=(20000,len(repos)))
    vals=np.asarray(sums)[draw].sum(axis=1)/np.asarray(counts)[draw].sum(axis=1)
    result['repository_cluster_percentile_95CI_G0_minus_E1_mean_pp']=np.quantile(vals,[.025,.975]).tolist()
    result['bootstrap']={'replicates':20000,'seed':20261023,'repo_order':repos,'estimand':'class-weighted mean difference; resample whole observed repositories; exploratory sensitivity, not a new NI or repeated-run CI'}
    mutants=[r['focal_mutants'] for r in rows if r['focal_mutants']>0]
    result['observed_focal_mutants']={'classes_with_nonempty_reports':len(mutants),'missing_or_empty':49-len(mutants),
        'min':min(mutants) if mutants else None,'median':statistics.median(mutants) if mutants else None,'max':max(mutants) if mutants else None,'mean':statistics.mean(mutants) if mutants else None}
    return result,repo_rows,[{'replicate':i+1,'repo_indices':';'.join(map(str,d)),'mean_difference_pp':float(v)} for i,(d,v) in enumerate(zip(draw,vals))]

def main():
    p=argparse.ArgumentParser();p.add_argument('--archive-root',type=Path,default=STAGE/'archive_final_v4');p.add_argument('--validate-only',action='store_true');a=p.parse_args()
    jobs,frozen,results=validate_inputs(a.archive_root)
    rows=[];diagnostics=[]
    for j,g,r in zip(jobs,frozen,results):
        row,diag=inspect_job(j,g,r,a.archive_root);rows.append(row);diagnostics.append(diag)
    stats,repos,draws=summarize(rows)
    print(json.dumps({'status':'PASS','n':49,'raw_job_audits':49,'GPT_guard':'PASS','no_primary_GPT_updates':True},ensure_ascii=False))
    if a.validate_only:return
    out=BASE/'outputs/e49_final_v2';out.mkdir(exist_ok=False)
    write_csv(out/'fixed49.csv',rows);write_json(out/'statistics.json',stats);write_json(out/'raw_diagnostics49.json',diagnostics)
    write_csv(out/'repository_summary.csv',repos);write_csv(out/'cluster_bootstrap_draws.csv',draws)
    diff=stats['G0_minus_E1'];ci=stats['repository_cluster_percentile_95CI_G0_minus_E1_mean_pp'];ct=stats['E1_counts']
    text=f'''# Kết quả E1 bổ sung trên fixed49 và giới hạn diễn giải

Đủ49 class/15 repository, toàn Maven, cùng cohort historical common-build. Không loại failures của E1;0 GPT API calls. G0 là dữ liệu archived, không tái đo;RQ1–RQ3 giữ nguyên. E0 assertions-off, E1 assertions/scaffold/runtime enabled.

| Thước đo trên cùng49 dòng | G0 archived | E0 archived | E1 pipeline |
|---|---:|---:|---:|
|Mean mutation (%)|{stats['G0_mean']:.2f}|{stats['E0_mean']:.2f}|{stats['E1_legacy_strict_mean']:.2f}|
|Median mutation (%)|{stats['G0_median']:.2f}|{stats['E0_median']:.2f}|{stats['E1_legacy_strict_median']:.2f}|

G0−E1 mean difference={diff['mean_pp']:.2f}pp; paired median difference={diff['median_pp']:.2f}pp. G0 higher/E1 higher/ties={diff['G_higher']}/{diff['E_higher']}/{diff['ties']}. Exploratory whole-repository bootstrap95% CI mean difference=[{ci[0]:.2f};{ci[1]:.2f}]pp,20.000draws/seed20261023.

E1 status counts: legacy process-build={ct['legacy_process_build']}/49; suites without recorded failures/errors={ct['suite_pass']}/49; complete suite/PIT/JaCoCo evidence flag={ct['measurement_evidence_complete']}/49; TestRule errors={ct['TestRule_missing']}/49. Skipped tests được báo riêng trongCSV; non_skipped_surefire_cases là số testcase Surefire không bịskip, gồm cả initializationError, không chứng nhận generated test method đã chạy. suite_pass gốc không trừ skipped. Evidence flag gốc không bao gồm process-build gate: đọc các cột cùng nhau, không gọi mọi flag là49 passing suites.

Không biến initialization failure thành phát biểu về chất lượng oracle. Các số pipeline giữ convention gate/zero-fill cũ; raw statuses không tạo thang P/C hoặc âm thầm chấm lại G0. Không dùng mean của một tập giao mới thay G0 trongRQ1–3.

Đây là sensitivity trên survivor cohort lịch sử, không phải đại diện buildability300, không tái xác nhận NI300 hoặc một kiểm định NI mới. Không ghép E1 của49 với E0 của251. Assertion/scaffold/runtime, explicit seed, native insertion và môi trường thực thi cùng khác E0: không quy chênh lệch cho riêng assertions. Một run/class không ước lượng within-arm variance. CI chỉ xử lý clustering của cohort này, không phải run-to-run variance.

Raw CSVs, XML, command/log hashes, generated bytes và POM files được kiểm độc lập trước xuất. Focal bytecode/mutant-multiset comparisons trong raw_diagnostics49.json chỉ so remaining historical snapshot, không chứng nhận cảhai arm lịch sử. CSV cols0–4 giữ duplicate nhưng không chứa đủ PIT index để định danh hoàn chỉnh mọi mutant.

Dữ liệu G0 lịch sử dùng process gate có thể chấp nhận Surefire failures; không tự chứng nhận mọi G0 suite pass. Lỗi runtime của E1 cần nêu và cân nhắc một compatibility protocol E-only riêng, không posthoc sửa điểm hoặc bỏ class.
'''
    with (out/'BAO_CAO_E49.md').open('x',encoding='utf-8') as f:f.write(text)
    en=f'''On the fixed49 historical common-build classes, archived GPT and supplementary EvoSuite pipeline mutation scores averaged{stats['G0_mean']:.2f}% and{stats['E1_legacy_strict_mean']:.2f}%, respectively. The paired mean difference was{diff['mean_pp']:.2f}percentage points (exploratory repository-bootstrap95% interval[{ci[0]:.2f},{ci[1]:.2f}]); directional counts were{diff['G_higher']}/{diff['E_higher']}/{diff['ties']}. All49 slots, including failures, were retained. This Maven-only configuration/runtime sensitivity uses unchanged archived GPT observations; it does not update RQ1–RQ3 or establish non-inferiority for the300-class benchmark. The changed EvoSuite integration and single run per class limit causal and variance interpretations. Runtime/evidence statuses are reported alongside scores.'''
    with (out/'paper_insert_en.md').open('x',encoding='utf-8') as f:f.write(en+'\n')
    inputs=[STAGE/'input_manifest49.json',STAGE/'protocol49.json',STAGE/'readiness_lock.json',STAGE/'results49.json',BASE/'outputs/paired49.csv',Path(__file__)]
    manifest={'inputs':{str(p.relative_to(BASE)):sha(p) for p in inputs},'outputs':{str(p.relative_to(out)):sha(p) for p in sorted(out.iterdir()) if p.is_file()},'original_files_modified':False}
    write_json(out/'output_manifest.json',manifest)
if __name__=='__main__':main()
