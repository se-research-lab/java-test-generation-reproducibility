"""Read-only liveness overlay; never writes status, starts or stops a process."""
import copy, json
from datetime import datetime, timezone
from pathlib import Path
import psutil
from maven_adapter_v1 import R

EXPECTED=(R/'src/run_remaining_maven167_v5.py').resolve()
PLAN=R/'launch_remaining_maven167_v5.json'
COMPLETE=R/'runtime/remaining_maven167_v5_completion.json'

def same_identity(identity,observed_creation,scripts):
    return (isinstance(identity,dict) and type(identity.get('pid')) is int and identity['pid']>0
            and type(identity.get('create_time')) in {float,int}
            and Path(identity.get('script','')).resolve()==EXPECTED
            and abs(float(identity['create_time'])-float(observed_creation))<.01
            and any(Path(s).resolve()==EXPECTED for s in scripts))

def probe(identity):
    if not isinstance(identity,dict) or type(identity.get('pid')) is not int or identity['pid']<=0:
        return 'UNKNOWN_INVALID_OWNER_RECORD'
    try:
        process=psutil.Process(identity['pid'])
        scripts=[s for s in process.cmdline() if s.lower().endswith('.py')]
        return 'PRESENT_MATCHED_PID_AND_CREATE_TIME' if same_identity(identity,process.create_time(),scripts) else 'ABSENT_OR_IDENTITY_CHANGED'
    except psutil.NoSuchProcess:
        return 'ABSENT_OR_IDENTITY_CHANGED'
    except (psutil.AccessDenied,ValueError,TypeError,OSError):
        return 'UNKNOWN_CANNOT_VERIFY_PROCESS'

def view_status(original):
    result=copy.deepcopy(original)
    result['live_process_check_at_utc']=datetime.now(timezone.utc).isoformat()
    if not PLAN.exists():
        result['runner_liveness']='NO_V5_OWNER_RECORD'
        # A stale phase must not be taken as a live worker without identity.
        if original.get('benchmark_admitted') or original.get('running'):
            result.update(snapshot_phase=original['phase'],phase='RUNNER_IDENTITY_UNAVAILABLE_REVIEW_REQUIRED',
                          running=0,active_sample_index=None,benchmark_admitted=False)
            result['blockers']=['Chưa có owner record v5 để xác minh tiến trình; không suy trạng thái RUNNING từ snapshot cũ']+list(result.get('blockers',[]))
        return result
    if COMPLETE.exists():
        result['runner_liveness']='INVOCATION_COMPLETION_RECORD_PRESENT'
        return result
    identity=json.loads(PLAN.read_text(encoding='utf-8')).get('runner_identity')
    health=probe(identity)
    result['runner_liveness']=health
    if health!='PRESENT_MATCHED_PID_AND_CREATE_TIME':
        result.update(snapshot_phase=original['phase'],phase='RUNNER_LIVENESS_REVIEW_REQUIRED',running=0,
                      active_sample_index=None,benchmark_admitted=False)
        result['blockers']=['Runner không được xác minh bằng PID/create-time/script; kiểm tra tiến trình và raw log trước mọi job mới; không tự restart']+list(result.get('blockers',[]))
    return result
