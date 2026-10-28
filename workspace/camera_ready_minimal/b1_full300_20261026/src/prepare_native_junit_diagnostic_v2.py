"""Preserve failed preflight, record verified log append, then version diagnostic."""
from pathlib import Path
import sys
from maven_adapter_v1 import R,dump,sha
from checkpoint_archive_guard_v1 import verify
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
old=R/'jobs/003_native_junit_diagnostic_v1'
assert old.is_dir() and not list(old.iterdir()),'First diagnostic should have stopped before copying/commands'
dump(old/'preflight_failure.json',{'status':'PRE_EXECUTION_ABORT','cause':'Full events hash differed due to exactly one post-archive JOB_TERMINAL append','no_commands_started':True,'new_generation_calls':0,'GPT_API_calls':0,'preserve_directory':True})
report=verify(R/'jobs/003');dump(R/'audit/checkpoint003_archive_reconciliation_v1.json',report)
source=R/'src/diagnose_native_junit_003_v1.py';target=R/'src/diagnose_native_junit_003_v2.py'
text=source.read_text(encoding='utf-8').replace('from run_maven_b1_v1 import guards','from run_maven_b1_v1 import guards\nfrom checkpoint_archive_guard_v1 import verify as verify_archive').replace("O=R/'jobs/003_native_junit_diagnostic_v1'","O=R/'jobs/003_native_junit_diagnostic_v2'")
text=text.replace("for row in original_manifest:ensure(sha(old/row['relative'])==row['sha256'],'Checkpoint evidence changed')","dump(O/'checkpoint_archive_reconciliation.json',verify_archive(old))")
text=text.replace("old/'artifact_manifest.json',old/'result.json']","old/'artifact_manifest.json',old/'result.json',R/'src/checkpoint_archive_guard_v1.py']")
text=text.replace("for row in original_manifest:ensure(sha(old/row['relative'])==row['sha256'],'Original checkpoint changed')","ensure(verify_archive(old)==report_before,'Original checkpoint changed')")
text=text.replace("original_manifest=load(old/'artifact_manifest.json')","original_manifest=load(old/'artifact_manifest.json');report_before=verify_archive(old)")
with target.open('x',encoding='utf-8') as f:f.write(text)
compile(text,str(target),'exec')
audit.log('B1_DIAGNOSTIC_PREFLIGHT_RECONCILED',report_sha256=sha(R/'audit/checkpoint003_archive_reconciliation_v1.json'),new_script_sha256=sha(target),new_experiment_calls=0)
print('PASS: checkpoint archive prefix and single terminal append verified; v1 failure preserved; v2 prepared')
