"""Create reviewed controller/dispatcher copies; leave admitted v1 sources intact."""
import sys,ast
from maven_adapter_v1 import R,dump,sha
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
def create(name,text):
 ast.parse(text)
 with (R/'src'/name).open('x',encoding='utf-8') as f:f.write(text)

text=(R/'src/maven_controller_v1.py').read_text(encoding='utf-8')
text=text.replace('from measurement_parser_v1 import parse','from measurement_parser_v1 import parse\nfrom native_junit_policy_candidate_v1 import patch as native_junit_patch,compare as native_junit_compare')
text=text.replace('gate=False;measurement_attempted=False;dep=None','gate=False;measurement_attempted=False;dep=None;native_junit_added=False')
text=text.replace("patch=policy_ns['patch_pom']", "native_junit_added=native_junit_patch(pom,out,beforedep)\n  patch=policy_ns['patch_pom']")
text=text.replace("if patch['changes']:","if patch['changes'] or native_junit_added:")
text=text.replace("policy_ns['compare_cp'](beforedep,dep,patch)","native_junit_compare(beforedep,dep) if native_junit_added else policy_ns['compare_cp'](beforedep,dep,patch)")
text=text.replace("'configuration':'E1_E49-compatible_Maven'","'configuration':'E1_Maven_native_JUnit_amendment_v2','native_junit_added':native_junit_added")
text=text.replace("dump(out/'result.json',result);archive(out);event('JOB_TERMINAL',class_key=j['class_key'],result_sha256=sha(out/'result.json'),artifact_manifest_sha256=sha(out/'artifact_manifest.json'));return result","dump(out/'result.json',result);event('JOB_TERMINAL',class_key=j['class_key'],result_sha256=sha(out/'result.json'));archive(out);return result")
create('maven_controller_v2.py',text)

text=(R/'src/run_maven_b1_v1.py').read_text(encoding='utf-8').replace('from maven_controller_v1 import execute,archive','from maven_controller_v2 import execute,archive\nfrom checkpoint_archive_guard_v2 import verify as verify_archive')
text=text.replace("path=R/'admission_maven_v1.json'","path=R/'admission_maven_v2.json'")
text=text.replace("r=load(out/'result.json');done.append(r)","r=load(R/'jobs/003_native_junit_diagnostic_v3/diagnostic_result.json') if j['sample_index_1based']==3 else load(out/'result.json');done.append(r)")
text=text.replace("calls+=r['generation_calls']","calls+=load(out/'result.json')['generation_calls']")
text=text.replace("(R/'jobs').glob('*/commands/*/plan.json')","(R/'jobs').glob('[0-9][0-9][0-9]/commands/*/plan.json')")
text=text.replace("if not (out/'artifact_manifest.json').exists():raise GuardAbort('Result without complete archive; explicit reconciliation required')","verify_archive(out)\n     if i==3:verify_archive(R/'jobs/003_native_junit_diagnostic_v3')")
text=text.replace("'Maven211 đang thực hiện theo thứ tự gốc; failures được giữ'","'Maven211 theo original order; native JUnit amendmentv2; failures được giữ'")
create('run_maven_b1_v2.py',text)
audit.log('B1_MAVEN_AMENDMENT_COPIES_PREPARED',controller_sha256=sha(R/'src/maven_controller_v2.py'),dispatcher_sha256=sha(R/'src/run_maven_b1_v2.py'),originals_unchanged=True)
print('Created controller v2 and dispatcher v2; not admitted yet')
