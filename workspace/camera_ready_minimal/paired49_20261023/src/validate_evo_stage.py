"""Independent final integrity and raw-artifact checks; no Java or model calls."""
import ast,csv,json,sys
from pathlib import Path
from xml.etree import ElementTree as ET
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit

def main():
    audit.verify()
    stage=BASE/'evo_patch'
    raw=json.loads((stage/'reports/raw49/copied_evidence.json').read_text(encoding='utf-8'))
    src=json.loads((stage/'reports/focal_counts49/source_copies.json').read_text(encoding='utf-8'))
    for r in raw+src:
        assert audit.sha(r['source'])==r['sha256']==audit.sha(BASE/r['copy']),r['source']
    manifest=json.loads((stage/'pre_edit_manifest.json').read_text(encoding='utf-8'))
    for r in manifest:
        assert audit.sha(BASE/r['backup'])==r['original_sha256']
        assert audit.sha(audit.ROOT/'scripts_v2/AgoneTest'/r['file'])==r['original_sha256']
        if r['file']!='mavenLib.py':assert audit.sha(BASE/r['working'])==r['original_sha256']
    old=ast.parse((stage/'backup/mavenLib.py').read_text(encoding='utf-8-sig'))
    new=ast.parse((stage/'working/AgoneTest/mavenLib.py').read_text(encoding='utf-8-sig'))
    funcs=lambda t:{x.name:ast.dump(x,include_attributes=False) for x in t.body if isinstance(x,(ast.FunctionDef,ast.ClassDef))}
    a,b=funcs(old),funcs(new)
    assert set(a)==set(b)
    changed=[k for k in a if a[k]!=b[k]];assert changed==['run_evosuite_generation_maven']
    fixture=json.loads((stage/'reports/scoped_fixture_result.json').read_text(encoding='utf-8'))
    assert fixture['status']=='PASS'
    for name,h in fixture['tool_hashes'].items():assert audit.sha(name)==h
    for name,h in fixture['generated_test_and_scaffold'].items():assert audit.sha(stage/'fixtures/scoped_runtime_08'/name)==h
    positive=(stage/'fixtures/scoped_runtime_08/junit_generated.stdout.txt').read_text(encoding='utf-8')
    negative=(stage/'fixtures/scoped_runtime_08/junit_mutant.stdout.txt').read_text(encoding='utf-8')
    assert 'OK (5 tests)' in positive and 'FAILURES!!!' in negative and 'expected:<10> but was:<11>' in negative
    maven=json.loads((stage/'reports/maven_fixture_v2_result.json').read_text(encoding='utf-8'))
    assert maven['status']=='PASS'
    xml=ET.parse(stage/'fixtures/maven_runtime_10/target/surefire-reports/TEST-fixture.BranchFixture_ESTest.xml').getroot()
    assert (int(xml.get('tests')),int(xml.get('failures')),int(xml.get('errors')),int(xml.get('skipped')))==(5,0,0,0)
    with (stage/'fixtures/maven_runtime_10/target/pit-reports/mutations.csv').open(encoding='utf-8',newline='') as f:mutants=list(csv.reader(f))
    assert len(mutants)==10 and sum(r[5]=='KILLED' for r in mutants)==7 and sum(r[5]=='SURVIVED' for r in mutants)==3
    with (stage/'fixtures/maven_runtime_10/target/site/jacoco/jacoco.csv').open(encoding='utf-8',newline='') as f:jac=list(csv.DictReader(f))
    assert len(jac)==1 and jac[0]['CLASS']=='BranchFixture' and int(jac[0]['BRANCH_COVERED'])==6
    for rel,h in maven['raw_artifact_hashes'].items():assert audit.sha(stage/'fixtures/maven_runtime_10'/rel)==h
    command_hashes=0
    for e in audit.events():
        if e['kind']=='COMMAND_END':
            for key in ['stdout','stderr']:assert audit.sha(BASE/e[key])==e[key+'_sha256']
            command_hashes+=1
    rec=[e for e in audit.events() if e['kind']=='MAVEN_FIXTURE_VALIDATED']
    assert audit.sha(stage/'reports/maven_fixture_result.json')==rec[0]['sha256']
    assert audit.sha(stage/'reports/maven_fixture_v2_result.json')==rec[1]['sha256']
    generations=[e for e in audit.events() if e['kind'] in ['FIXTURE_COMMAND_START','SCOPED_FIXTURE_START'] and e.get('name')=='generate']
    assert len(generations)==2
    report={'status':'PASS','protected_originals_and_backups':585,'extra_archived_raw_files_verified':len(raw),
        'remaining_focal_source_snapshots_verified':len(src),'only_original_function_changed_in_copy':changed,
        'original_experiment_files_modified':0,'shared_copied_files_unchanged':5,
        'completed_command_log_pairs_verified':command_hashes,'synthetic_generation_attempts':len(generations),
        'synthetic_Maven_integration_attempts':2,'benchmark_classes_generated':0,'GPT_API_calls':0,
        'same_generated_bytes_and_tools_verified':True,'direct_JUnit_positive_and_mutant_control':'PASS',
        'Maven_raw_Surefire_PIT_JaCoCo':'PASS','derived_summary_recovery_hash_verified':True,
        'still_pending':['actual E-only driver integration','benchmark scope/seed/timeout freeze','arm-specific raw validity'],
        'scope':'Integrity and synthetic functionality checks, not certification of historical scientific validity'}
    out=stage/'reports/final_validation.json';assert not out.exists()
    out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    audit.log('EVO_STAGE_FINAL_VALIDATION',path=str(out.relative_to(BASE)),sha256=audit.sha(out),status='PASS')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
