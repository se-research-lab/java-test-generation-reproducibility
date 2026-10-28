"""Meaningful negative checks of isolation, selected suite, missing evidence and timeout."""
import importlib.util,json,subprocess,sys,types
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
spec=importlib.util.spec_from_file_location('eonly',BASE/'src/e49_driver.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
out=BASE/'e49_driver/semantic_checks_01';out.mkdir(exist_ok=False)
# All imports and helpers use the actual driver; no Java/API requests are made here.
safety=driver.validate_safety()
module=out/'repo';module.mkdir();sr=module/'target/surefire-reports';sr.mkdir(parents=True)
(sr/'TEST-fixture.BranchFixture_ESTest.xml').write_text('<testsuite name="fixture.BranchFixture_ESTest" tests="1" failures="1" errors="0" skipped="0"/>')
r=driver.raw_metrics(module,'fixture.BranchFixture_ESTest','BranchFixture','fixture',True)
assert r['legacy_process_build']==1 and r['suite_pass'] is False and r['mutation_score_percent'] is None and r['legacy_strict_mutation_percent']==0
# Removing all reports must not make a stale successful score appear.
empty=out/'empty';empty.mkdir();r2=driver.raw_metrics(empty,'fixture.BranchFixture_ESTest','BranchFixture','fixture',False)
assert r2['legacy_strict_mutation_percent']==0 and not r2['measurement_evidence_complete']
(sr/'TEST-unrelated.xml').write_text('<testsuite name="unrelated.GPTTest" tests="1" failures="0" errors="0" skipped="0"/>')
r3=driver.raw_metrics(module,'fixture.BranchFixture_ESTest','BranchFixture','fixture',True)
assert not r3['only_selected_suite_executed'] and not r3['measurement_evidence_complete']
class TimeoutCommands:
    TimeoutExpired=subprocess.TimeoutExpired
    def run(self,argv,**kw):
        if '-jar' in argv:raise subprocess.TimeoutExpired(argv,240,output='timeout-control',stderr='')
        target=Path(kw['cwd'])/'target';(target/'classes').mkdir(parents=True,exist_ok=True)
        return subprocess.CompletedProcess(argv,0,'compile-control','')
cmd=TimeoutCommands();ns,phases=driver.load_functions(cmd,out)
focal=module/'src/main/java/fixture/BranchFixture.java';focal.parent.mkdir(parents=True);focal.write_text('package fixture; public class BranchFixture {}')
assert ns['run_evosuite_generation_maven'](str(module),str(focal),'Windows',generation_profile=driver.evosuite_profile.REVIEWER) is False
assert any(p['status']=='ERROR' and '240' in p['detail'] for p in phases)
# A command outside the new job is rejected before invoking a subprocess.
controller=driver.Commands(out,{},BASE,123)
try:controller.run(['java','-version'],cwd=audit.ROOT)
except AssertionError:pass
else:raise AssertionError('Outside-job command was accepted')
report={'status':'PASS','driver_sha256':audit.sha(BASE/'src/e49_driver.py'),
 'GPT_imports_absent':True,'legacy_gate_preserved_with_failing_XML':True,
 'missing_report_cannot_reuse_old_score':True,'foreign_suite_detected':True,
 'generation_timeout_propagates_failure':True,'outside_job_command_rejected':True,
 'actual_Java_or_Maven_commands':0,'limit':'Negative controls only; actual driver fixture still required'}
driver.write_json(out/'result.json',report);print(json.dumps(report,indent=2))
