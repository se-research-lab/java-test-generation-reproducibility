"""Read-only reconciliation of a finished timeout. No experiment, old archive unchanged."""
import json,sys
from pathlib import Path
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump
from checkpoint_archive_guard_v2 import verify
from measurement_parser_completion_v2 import parse
A=R/'completion_amendment_v1'
def load(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def main():
 old=R/'jobs/112_completion_pom_v2';out=A/'result_reconciliations_v1/112';out.mkdir(parents=True,exist_ok=False)
 check=verify(old);job=load(old/'job_admission.json')['job'];last=load(old/'commands/007/finished.json');assert last['reason']=='TIMEOUT' and load(old/'commands/007/plan.json')['timeout_seconds']==300
 assert load(old/'production_bytecode_guard.json')=={'changed':[],'added':[],'missing':[],'baseline_available':True}
 suite=load(old/'native_generated.json');assert suite['complete'];assert all(sha(x['path'])==x['sha256'] for x in suite['files'])
 raw=parse(old/'repo'/job['module'],job['focal_class'],job['package'],job['selected_test_fqcn'],False)
 assert raw['strict_suite_evidence'] and raw['mutation_score_percent'] is None
 record={'sample_index_1based':112,'class_key':job['class_key'],'repo_id':job['repo_id'],'seed':job['seed'],'configuration':'unchanged_E1_POM_attempt_reconciled_after_measurement_timeout','raw_job_path':str(old.resolve()),'raw_archive_sha256':sha(old/'artifact_manifest.json'),'raw_result_missing_because':'legacy parser assertion on truncated report after300s timeout','generation_success':True,'generation_calls':1,'measurement_attempted':True,'terminal':True,'source_guard':'PASS_AT_CONTROLLER_BEFORE_PARSER','production_bytecode_guard':'PASS','GPT_API_calls':0,'reconciliation_only_no_rerun':True,'PIT_stage':'TIMEOUT_PARTIAL_REPORT_REJECTED','compile_test':'PASS_XML','test_execution':'PASS','end_to_end_score_percent':0.0,'score_basis':'CONVENTIONAL_END_TO_END_MEASUREMENT_TIMEOUT_ZERO_NOT_OBSERVED_MUTATION',**raw}
 dump(out/'result.json',record);dump(out/'reconciliation.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'original_job_archive_check':check,'original_archive_path':str(old/'artifact_manifest.json'),'original_archive_sha256':sha(old/'artifact_manifest.json'),'result_sha256':sha(out/'result.json'),'selection_rule':'original single attempt, fixed timeout300; no highest-score selection','original_job_modified':False,'new_generation_calls':0,'new_measurement_calls':0,'raw_report_not_modified':True})
 print('Reconciled112: native tests pass; PIT timeout; observed mutation null; conventional E2E zero')
if __name__=='__main__':main()
