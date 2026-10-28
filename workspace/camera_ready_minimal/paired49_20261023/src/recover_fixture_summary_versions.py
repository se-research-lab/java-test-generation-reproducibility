"""Recover an accidentally reused derived summary path from hash-verified command stdout.

All raw attempt09/10 reports and stdout/stderr were separate and untouched.
This records the audit deviation rather than hiding it.
"""
import json,shutil,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit

current=BASE/'evo_patch/reports/maven_fixture_result.json'
v2=BASE/'evo_patch/reports/maven_fixture_v2_result.json'
assert not v2.exists()
records=[e for e in audit.events() if e['kind']=='MAVEN_FIXTURE_VALIDATED']
assert len(records)==2 and [e['status'] for e in records]==['FAIL','PASS']
assert audit.sha(current)==records[1]['sha256']
shutil.copy2(current,v2);assert audit.sha(current)==audit.sha(v2)
audit.log('DERIVED_SUMMARY_BACKUP_BEFORE_RECOVERY',source=str(current.relative_to(BASE)),backup=str(v2.relative_to(BASE)),sha256=audit.sha(v2))
stdout=BASE/'audit/maven_fixture09.stdout.txt'
command=next(e for e in audit.events() if e['kind']=='COMMAND_END' and e['name']=='maven_fixture09')
assert audit.sha(stdout)==command['stdout_sha256']
obj=json.loads(stdout.read_text(encoding='utf-8'))
recovered=json.dumps(obj,indent=2)+'\n'
recovery=BASE/'evo_patch/reports/maven_fixture_v1_recovered.json'
assert not recovery.exists()
recovery.write_text(recovered,encoding='utf-8')
assert audit.sha(recovery)==records[0]['sha256'],'Recovery must match the exact pre-overwrite digest'
before=audit.sha(current);current.write_bytes(recovery.read_bytes())
audit.log('AUDIT_DEVIATION_RECOVERED',
    event='Attempt10 reused the attempt09 derived summary filename without a pre-overwrite backup; raw reports and command logs were never overwritten.',
    scope='synthetic fixture summary JSON only; no original experiment, generated tests or scientific dataset affected',
    recovery='Attempt09 exact bytes recovered from its preserved stdout and verified against its pre-overwrite ledger SHA256; attempt10 backed up under unique v2 filename before restoration.',
    restored_path=str(current.relative_to(BASE)),before_sha256=before,after_sha256=audit.sha(current),
    unique_attempt10_path=str(v2.relative_to(BASE)),unique_attempt10_sha256=audit.sha(v2),
    rule='All subsequent artifact writers must refuse existing report paths and use attempt-specific filenames.')
print(json.dumps({'attempt09_exact_bytes_restored':True,'attempt10_unique_summary':str(v2),'raw_evidence_untouched':True},indent=2))
