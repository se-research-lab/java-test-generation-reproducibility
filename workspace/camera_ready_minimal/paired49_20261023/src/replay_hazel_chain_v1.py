"""Trace the inherited Hazelcast Surefire execution chain without any POM patch."""
import importlib.util,json,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
SOURCE=BASE/'src/replay_e1_discovery_runtime_v2.py';assert audit.sha(SOURCE)=='a8a80c71c4042cb34e3fef27ed6abc283715ccd48bf208f8b10544599c12b386'
spec=importlib.util.spec_from_file_location('discovery_locked_v2',SOURCE);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
assert sys.argv[1]=='hazel_chain';job=sys.argv[2];assert job in ['18','19']
mod=helper.mod;out,info,module,commands,args,attempt=mod.context(job)
assert (out/'hazel_direct_result.json').exists() and not (out/'hazel_chain_result.json').exists()
helper.preserve_prior_reports(module,attempt)
plan={'job':job,'operation':'unchanged inherited test lifecycle with debug log','POM_patch':False,'skip_overrides_added':False,'purpose':'Contrast original multiple Surefire executions with the single regular execution; no PIT or new score'}
mod.dump(attempt/'chain_plan.json',plan);audit.log('E1_COMPATIBILITY_HAZEL_CHAIN_PLAN',sha256=audit.sha(attempt/'chain_plan.json'),job=job)
r=commands.run([*args,'-X','test'],cwd=module,timeout=300)
report={'job':job,'kind':'unchanged inherited execution-chain trace','command_returncode':r.returncode,**helper.postchecks(out,info,module)}
helper.snapshot_reports(module,attempt/'surefire_archive')
stdout=commands.records[-1]['stdout'];text=(BASE/stdout).read_text(encoding='utf-8')
report['discovery_trace_lines']=[s for s in text.splitlines() if any(token in s for token in ['Tests are skipped','Tests run:','already been run','skip =','groups =','excludedGroups =','test =','maven-surefire-plugin:2.17:test'])]
mod.dump(out/'hazel_chain_result.json',report)
audit.log('E1_COMPATIBILITY_HAZEL_CHAIN_COMPLETE',job=job,report_sha256=audit.sha(out/'hazel_chain_result.json'),suite_pass=report['selected_suite_all_methods_pass'])
print(json.dumps({'job':job,'command_returncode':r.returncode,'selected_suite_all_methods_pass':report['selected_suite_all_methods_pass'],'XML_suites':report['XML_suites'],'trace':report['discovery_trace_lines']},indent=2))
