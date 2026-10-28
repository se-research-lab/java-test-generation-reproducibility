"""Sequential audited compatibility runner, with post-POM and XML guards."""
import importlib.util,json,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
SOURCE=BASE/'src/diagnose_e1_compatibility_v4.py'
assert audit.sha(SOURCE)=='82ad00778ff7cb423f16051ede46d316238dbf45b354e90d9216ca20a9517ed9'
spec=importlib.util.spec_from_file_location('compatibility_locked_v4',SOURCE);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
job=sys.argv[1];assert job in ['09','12','13','14','15']
mod.junit(job)
out=mod.STAGE/'jobs'/job;info=mod.load(out/'input.json');patch=mod.load(out/'junit_patch.json')
assert audit.sha(out/'repo'/info['module_relative']/'pom.xml')==patch['after_sha256'],'Unexpected post-run POM drift'
result=mod.load(out/'diagnostic_result.json');suites=result['XML_suites']
strict=bool(suites) and all(s['name']==info['selected_test_fqcn'] and s['tests']>0 and s['errors']+s['failures']+s['skipped']==0 for s in suites) and result['selected_suite_all_methods_pass']
mod.dump(out/'strict_acceptance.json',{'job':job,'post_POM_hash':'PASS','XML_suite_and_case_checks_pass':strict,'source_and_production_bytecode_unchanged':not result['source_issues'] and not result['production_class_mismatches'],'diagnostic_only':True,'E1_scores_replaced':False})
audit.log('E1_COMPATIBILITY_C01_POSTCHECK',job=job,strict_pass=strict,report_sha256=audit.sha(out/'strict_acceptance.json'),E1_scores_replaced=False)
print(json.dumps({'job':job,'strict_acceptance':strict,'E1_scores_replaced':False}))
