"""Version the diagnostic to permit the legacy helper's read-only java -version."""
import sys
from maven_adapter_v1 import R,dump,sha
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
source=R/'src/diagnose_native_junit_003_v2.py';target=R/'src/diagnose_native_junit_003_v3.py'
text=source.read_text(encoding='utf-8').replace("003_native_junit_diagnostic_v2'","003_native_junit_diagnostic_v3'")
text=text.replace("ensure(Path(str(argv[0])).name.lower() in {'mvn','mvn.cmd'},'Diagnostic forbids Java/generation/API')","ensure(Path(str(argv[0])).name.lower() in {'mvn','mvn.cmd'} or (Path(str(argv[0])).name.lower() in {'java','java.exe'} and list(argv[1:])==['-version']),'Diagnostic forbids generation/API; permits only read-only java -version')")
with target.open('x',encoding='utf-8') as f:f.write(text)
compile(text,str(target),'exec')
dump(R/'audit/native_junit_diagnostic_v2_recovery.json',{'prior_status':'ABORTED_BEFORE_MEASUREMENT','reason':'Measurement-only guard rejected unchanged legacy java -version sanity check','commands_started':6,'generation_calls':0,'GPT_API_calls':0,'existing_evidence_preserved':True,'next_version_sha256':sha(target),'next_change':'permit exact java -version only; generation still forbidden'})
audit.log('B1_NATIVE_JUNIT_DIAGNOSTIC_SANITYCHECK_FIX',report_sha256=sha(R/'audit/native_junit_diagnostic_v2_recovery.json'),new_script_sha256=sha(target));print('Prepared v3; previous pre-measurement failure preserved')
