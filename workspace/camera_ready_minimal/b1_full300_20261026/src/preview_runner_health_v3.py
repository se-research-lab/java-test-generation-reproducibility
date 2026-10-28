"""Read-only liveness for the sealed Gradle40 owner; retain Maven fallback."""
import copy,json
from datetime import datetime,timezone
from pathlib import Path
from maven_adapter_v1 import R,sha
from preview_runner_health_v2 import probe,view_status as maven_view

def view_status(original):
 owner=R/'runtime/gradle_full40_v1/owner.json'
 if not owner.exists():
  result=maven_view(original);result['monitor_implementation']='read_only_v5_gradle_aware';return result
 result=copy.deepcopy(original);identity=json.loads(owner.read_text(encoding='utf-8'))
 result.update(monitor_implementation='read_only_v5_gradle_aware',runner_invocation_version='Gradle policy v1 / dispatcher v2',live_process_check_at_utc=datetime.now(timezone.utc).isoformat())
 script=R/'src/run_gradle_full40_v2.py';admission=R/'admission_gradle_full40_v1.json'
 pins=identity.get('script_sha256')==sha(script) and identity.get('admission_sha256')==sha(admission)
 complete=owner.parent/'complete.json';interrupted=owner.parent/'interrupted.json'
 if pins and complete.exists() and json.loads(complete.read_text(encoding='utf-8')).get('admission_sha256')==sha(admission):
  result.update(runner_liveness='INVOCATION_COMPLETION_RECORD_PRESENT',running=0,active_sample_index=None);return result
 health=probe(identity,script) if pins else 'UNKNOWN_OWNER_PLAN_PIN_DRIFT'
 result['runner_liveness']=health
 if interrupted.exists() or health!='PRESENT_MATCHED_PID_AND_CREATE_TIME':
  result.update(snapshot_phase=original['phase'],phase='GRADLE_RUNNER_REVIEW_REQUIRED',running=0,active_sample_index=None,benchmark_admitted=False)
  result['blockers']=['Gradle invocation interrupted or exact PID/start-time/source not verified; no automatic restart']+list(result.get('blockers',[]))
 return result
