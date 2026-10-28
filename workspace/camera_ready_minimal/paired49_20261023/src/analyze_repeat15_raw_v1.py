"""Independent raw reconstruction and descriptive repeated15x5 analysis. No generation imports/API calls."""
import argparse,ast,csv,hashlib,io,json,math,re,statistics,sys,zipfile
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree as ET
import numpy as np
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
ST=B/'repeated_subset_v1';OUT=ST/'analysis_v1';sha=audit.sha

def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def save(p,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def summarize(values):
    v=list(map(float,values));assert len(v)==5
    return {'raw':v,'mean':statistics.mean(v),'median':statistics.median(v),'sample_SD':statistics.stdev(v),'min':min(v),'max':max(v),'range':max(v)-min(v)}
def across(values):
    a=np.asarray(values,dtype=float);return {'n':len(a),'mean':float(a.mean()),'median':float(np.median(a)),'q25':float(np.quantile(a,.25)),'q75':float(np.quantile(a,.75)),'min':float(a.min()),'max':float(a.max())}
def read_member(z,name):return z.read(name).decode('utf-8-sig',errors='replace')
def csv_member(z,name):return list(csv.reader(io.StringIO(read_member(z,name)))) if name in z.namelist() else []

def controls():
    x=summarize([0,0,0,0,100]);assert x['mean']==20 and x['range']==100 and math.isclose(x['sample_SD'],math.sqrt(2000))
    x=summarize([0]*5);assert x['sample_SD']==0 and x['mean']==0
    # Replicates stay in their class; resampling classes, not75independent runs.
    a=np.array([[0]*5,[100]*5],float);cm=a.mean(axis=1);rng=np.random.default_rng(20261024);idx=rng.integers(0,2,size=(1000,2));v=cm[idx].mean(axis=1);assert set(v)=={0,50,100}
    print(json.dumps({'status':'PASS','checks':['sample_SD_ddof1','zero_variance_all_fail_is_not_adequacy','cluster_bootstrap_preserves_replicates'],'API_calls':0}))

def run():
    assert load(ST/'complete.json')['status']=='COMPLETE','All150 scheduled slots must finish before analysis'
    assert not OUT.exists();schedule=load(ST/'schedule150.json');jobs={j['class_key']:j for j in load(ST/'input_jobs15.json')};prompts={r['class_key']:r for r in load(ST/'prompts15.json')}
    assert len(schedule)==150 and len(jobs)==15 and Counter(s['arm'] for s in schedule)=={'G':75,'E':75}
    core=load(ST/'readiness_lock.json')
    for n,h in core['code_and_input_hashes'].items():assert sha(B/n)==h,n
    for n,h in core['external_hashes'].items():assert sha(n)==h,n
    results=load(ST/'results150.json');assert [r['slot_id'] for r in results]==[s['slot_id'] for s in schedule]
    reconstructed=[];archive_members_checked=0;inputs={};issues=[];api_usage=[]
    for slot,r in zip(schedule,results):
        out=ST/'slots'/slot['slot_id'];j=jobs[slot['class_key']];done=load(out/'complete.json');assert done['status']=='COMPLETE' and done['result_sha256']==sha(out/'result.json') and load(out/'result.json')==r
        am=load(out/'archive_manifest.json');archive=out/'slot_archive.zip';assert sha(archive)==am['archive_sha256'];inputs[str(archive.relative_to(B))]=sha(archive)
        with zipfile.ZipFile(archive) as z:
            names=z.namelist();assert len(names)==len(set(names))==len(am['files'])
            for item in am['files']:assert hashlib.sha256(z.read(item['path'])).hexdigest()==item['sha256'],item['path']
            archive_members_checked+=len(names);assert json.loads(read_member(z,'result.json'))==r
            admission=json.loads(read_member(z,'slot_admission.json'));assert admission['slot']==slot and admission['lock_sha256']==sha(ST/'readiness_lock.json')
            expected_test=j['selected_test_fqcn'] if slot['arm']=='E' else (j['package']+'.' if j['package'] else '')+Path(j['old_synthesized_test_relative']).stem
            module='repo/'+j['module'].replace('\\','/').strip('/')
            # Check source observations directly in the archived full workspace.
            assert hashlib.sha256(z.read('repo/'+j['focal_path'])).hexdigest()==j['focal_sha256']
            original={s['relative']:s['sha256'] for s in j['source_files']};allowed={j['old_synthesized_test_relative'],j['module']+'/pom.xml',*r['generated_sources']}
            for n,h in original.items():
                if n in allowed:continue
                assert hashlib.sha256(z.read('repo/'+n)).hexdigest()==h,n
            assert hashlib.sha256(z.read('settings.xml')).hexdigest()==j['settings_sha256']
            for n,h in r['generated_sources'].items():assert hashlib.sha256(z.read('repo/'+n)).hexdigest()==h
            classprefix=module+'/target/classes/';current={n[len(classprefix):]:hashlib.sha256(z.read(n)).hexdigest() for n in names if n.startswith(classprefix) and n.endswith('.class')}
            baseline={n:q['sha256'] for n,q in j['production_baseline'].items()};assert not set(current)-set(baseline)
            assert all(current[n]==baseline[n] for n in current)
            commands=[json.loads(read_member(z,n)) for n in names if re.fullmatch(r'command_\d+\.json',n)]
            for cmd in commands:
                prefix=f"command_{cmd['index']:02d}";assert hashlib.sha256(z.read(prefix+'.stdout.txt')).hexdigest()==cmd['stdout_sha256'];assert hashlib.sha256(z.read(prefix+'.stderr.txt')).hexdigest()==cmd['stderr_sha256']
                assert str(out.resolve()).lower() in cmd['cwd'].lower(),'Command outside intended new slot'
            goals=['clean','verify','jacoco:prepare-agent','jacoco:report','org.pitest:pitest-maven:mutationCoverage'];measure=[c for c in commands if c['argv'][-5:]==goals];assert len(measure)<=1
            if measure:
                c=measure[0];stdout=read_member(z,f"command_{c['index']:02d}.stdout.txt");gate=bool('BUILD SUCCESS' in stdout and not c['timeout'])
            else:gate=False
            if gate:assert set(current)==set(baseline),'Process success but missing production class'
            mrows=csv_member(z,module+'/target/pit-reports/mutations.csv');assert all(len(q)==7 for q in mrows)
            focal=[q for q in mrows if q[0].replace('.java','')==j['focal_class'] and (q[1].rsplit('.',1)[0] if '.' in q[1] else '')==j['package']]
            assert not [q for q in mrows if q[5]=='KILLED' and expected_test not in q[6]],'Unexpected killing test'
            killed=sum(q[5]=='KILLED' for q in focal);score=round(100*killed/len(focal),2) if gate and focal else 0.0
            assert int(gate)==r['legacy_process_build'] and score==r['legacy_strict_mutation_percent']
            assert len(focal)==r['focal_mutants'] and killed==r['killed_mutants']
            ids=Counter(tuple(q[:5]) for q in focal);fp=hashlib.sha256(json.dumps(sorted([list(k)+[v] for k,v in ids.items()]),separators=(',',':')).encode()).hexdigest() if focal else None
            # Report completeness against archived reference counts; do not change a legacy score.
            baseline_n=j['focal_mutants_baseline']['n'];count_matches=bool(focal and len(focal)==baseline_n)
            cases=[]
            for n in names:
                if n.startswith(module+'/target/surefire-reports/TEST-') and n.endswith('.xml'):
                    root=ET.fromstring(z.read(n))
                    for c in root.findall('testcase'):cases.append({'suite':root.get('name'),'class':c.get('classname'),'name':c.get('name'),'failures':len(c.findall('failure')),'errors':len(c.findall('error')),'skipped':len(c.findall('skipped'))})
            strict_execution=bool(cases) and all(c['suite']==expected_test and c['class']==expected_test and c['failures']+c['errors']+c['skipped']==0 for c in cases)
            jacrows=[];jacname=module+'/target/site/jacoco/jacoco.csv'
            if jacname in names:jacrows=list(csv.DictReader(io.StringIO(read_member(z,jacname))))
            jacf=[q for q in jacrows if q.get('CLASS')==j['focal_class'] and q.get('PACKAGE','').replace('/','.')==j['package']]
            gen=[c for c in commands if '-jar' in c['argv']];api_attempts=[]
            if slot['arm']=='E':
                assert len(gen)<=2 and not any(re.fullmatch(r'api_request\.json',n) for n in names)
                for c in gen:
                    argv=c['argv'];assert argv[argv.index('-seed')+1]==str(slot['seed'])
                    for option in ['-Dassertions=true','-Dtest_scaffolding=true','-Dno_runtime_dependency=false','-Dcriterion=BRANCH','-Dsearch_budget=60','-Dtest_archive=false','-Duse_separate_classloader=false']:assert option in argv,option
                    assert any('MUTATION' in a and 'assertion' in a for a in argv)
            else:
                assert not gen and not r['policy']['changes']
                if 'api_request.json' in names:
                    req=json.loads(read_member(z,'api_request.json'));assert req=={'model':'gpt-4o-mini-2024-07-18','messages':prompts[slot['class_key']]['messages'],'temperature':0,'top_p':1,'max_tokens':2048,'stream':False}
                    assert digest(req['messages'])==j['messages_sha256']
                    for n in sorted(names):
                        if re.fullmatch(r'api_attempt\d+\.json',n):api_attempts.append(json.loads(read_member(z,n)))
                    assert 1<=len(api_attempts)<=5
                    oks=[a for a in api_attempts if a['status']=='OK'];assert len(oks)<=1
                    for a in oks:
                        obj=json.loads(read_member(z,f"api_response_attempt{a['attempt']}.json"));assert obj['model']=='gpt-4o-mini-2024-07-18';api_usage.append(obj.get('usage') or {})
            assert len(gen)==r['EvoSuite_generation_attempts'] and len(api_attempts)==r['GPT_API_attempts']
            row={**slot,'selected_test_fqcn':expected_test,'generation_success':r['generation_success'],'legacy_process_build':int(gate),'strict_mutation_percent':score,'focal_mutants':len(focal),'killed':killed,'focal_count_matches_E49_reference':count_matches,'raw_focal_ID_diagnostic_sha256':fp,'PIT_report_present':module+'/target/pit-reports/mutations.csv' in names,'JaCoCo_focal_present':bool(jacf),'canonical_cases':cases,'complete_execution_without_failure_error_skip':strict_execution,'complete_report_execution_evidence':bool(strict_execution and focal and jacf),'generated_source_set_sha256':digest(r['generated_sources']),'generation_source_members':r['generated_sources'],'GPT_API_attempts':len(api_attempts),'EvoSuite_generation_attempts':len(gen),'generation_duration_seconds_including_compile':r['generation_duration_seconds_including_compile'],'measurement_duration_seconds':r['measurement_duration_seconds'],'archive_sha256':sha(archive)};reconstructed.append(row)
    assert len(reconstructed)==150
    classes=[]
    for j in sorted(jobs.values(),key=lambda x:x['repo_id']):
        entry={k:j[k] for k in ['job_index','repo_id','class_key','focal_class']}
        for arm in ['G','E']:
            rows=sorted([r for r in reconstructed if r['class_key']==j['class_key'] and r['arm']==arm],key=lambda r:r['replicate']);assert [r['replicate'] for r in rows]==[1,2,3,4,5]
            entry[arm]={**summarize([r['strict_mutation_percent'] for r in rows]),'slot_ids':[r['slot_id'] for r in rows],'build_count':sum(r['legacy_process_build'] for r in rows),'generation_success_count':sum(r['generation_success'] for r in rows),'complete_evidence_count':sum(r['complete_report_execution_evidence'] for r in rows),'unique_generated_source_sets':len({r['generated_source_set_sha256'] for r in rows}),'all_zero_pipeline_scores':all(r['strict_mutation_percent']==0 for r in rows)}
        entry['paired_class_mean_G_minus_E_pp']=entry['G']['mean']-entry['E']['mean'];classes.append(entry)
    means=np.array([r['paired_class_mean_G_minus_E_pp'] for r in classes]);rng=np.random.default_rng(20261024);indices=rng.integers(0,15,size=(20000,15));draws=means[indices].mean(axis=1);ci=np.quantile(draws,[.025,.975]).tolist()
    stats={'n_classes':15,'repositories':15,'replicates_per_arm_class':5,'n_scheduled_slots':150,'primary_RQ_membership_unchanged':True,'bootstrap':{'replicates':20000,'seed':20261024,'unit':'whole class/repository with all5runs,botharms','class_order':[r['class_key'] for r in classes]},'paired_class_means_G_minus_E':{'mean_pp':float(means.mean()),'median_pp':float(np.median(means)),'G_higher':int(np.sum(means>1e-9)),'E_higher':int(np.sum(means< -1e-9)),'ties':int(np.sum(np.abs(means)<=1e-9)),'exploratory_cluster95CI_mean_pp':ci},'arms':{},'generation_API_calls_by_this_analysis':0,'new_NI_test':False}
    for arm in ['G','E']:
        raw=[r for r in reconstructed if r['arm']==arm];v=[r[arm] for r in classes];stats['arms'][arm]={'runs':75,'process_builds':sum(r['legacy_process_build'] for r in raw),'generation_successes':sum(r['generation_success'] for r in raw),'complete_report_execution_evidence':sum(r['complete_report_execution_evidence'] for r in raw),'class_mean_score_distribution':across([c['mean'] for c in v]),'within_class_sample_SD_pp':across([c['sample_SD'] for c in v]),'within_class_range_pp':across([c['range'] for c in v]),'all_zero_classes':sum(c['all_zero_pipeline_scores'] for c in v),'mixed_build_classes':sum(0<c['build_count']<5 for c in v),'all5_build_classes':sum(c['build_count']==5 for c in v),'API_POST_attempts':sum(r['GPT_API_attempts'] for r in raw),'EvoSuite_search_attempts':sum(r['EvoSuite_generation_attempts'] for r in raw)}
    stats['API_usage']={'successful_response_count':len(api_usage),'prompt_tokens':sum(x.get('prompt_tokens',0) for x in api_usage),'completion_tokens':sum(x.get('completion_tokens',0) for x in api_usage),'total_tokens':sum(x.get('total_tokens',0) for x in api_usage),'cost_estimate_uncached_USD':sum((x.get('prompt_tokens',0)*.15+x.get('completion_tokens',0)*.60)/1e6 for x in api_usage),'not_invoice':True}
    OUT.mkdir();save(OUT/'raw_reconstructed150.json',reconstructed);save(OUT/'per_class15.json',classes);save(OUT/'statistics.json',stats);save(OUT/'bootstrap_draws20000.json',draws.tolist());save(OUT/'raw_audit.json',{'status':'PASS','archive_files':150,'archive_members_SHA_checked':archive_members_checked,'raw_measurement_scores_match_driver_all150':True,'source_production_and_settings_checks':'PASS','model_prompt_parameters_and_E_profile_checks':'PASS','primary_data_modified':False,'scope':'same legacy pipeline scores plus independent execution/report diagnostics; no inference of oracle adequacy from process gate','inputs':inputs})
    # A compact table for the manuscript; no automatic manuscript edits.
    lines=['Arm | Runs | Process-build | Median within-class SD (pp) | Maximum within-class range (pp)','--- | ---: | ---: | ---: | ---:']
    for arm,label in [('G','GPT-repeat'),('E','E1-repeat')]:
        a=stats['arms'][arm];lines.append(f"{label} |75|{a['process_builds']}/75|{a['within_class_sample_SD_pp']['median']:.2f}|{a['within_class_range_pp']['max']:.2f}")
    report='# Repeated subset:15class×5runs/arm\n\n'+'\n'.join(lines)+'\n\nAll150 scheduled slots are retained. Scores use the original process gate and zero-fill. SD=0 may represent five identical failures or zero scores, not stable behavioral adequacy. Repeats are nested in15classes/repositories;75runs per arm are not75independent classes. This supplement leaves primary GPT61/45/300 and E49 unchanged and does not establish E1 full300 NI.\n'
    (OUT/'RESULTS_SUMMARY.md').write_text(report,encoding='utf-8');audit.log('REPEAT15_RAW_ANALYSIS_COMPLETE',n=150,classes=15,archives=150,archive_members_checked=archive_members_checked,statistics_sha256=sha(OUT/'statistics.json'),API_calls=0)
    print(json.dumps({'status':'PASS','classes':15,'runs':150,'statistics':stats},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['controls','run']);args=p.parse_args();controls() if args.mode=='controls' else run()
