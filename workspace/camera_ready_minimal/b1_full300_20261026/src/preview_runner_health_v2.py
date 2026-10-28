"""Read-only display health for exactly the admitted v5/v6 owner records."""
import copy,json
from datetime import datetime,timezone
from pathlib import Path
import psutil
from maven_adapter_v1 import R,sha

OWNERS=[('v6','remaining_maven153_v6','run_remaining_maven153_v6.py'),
        ('v5','remaining_maven167_v5','run_remaining_maven167_v5.py')]

def same_owner(identity,creation,scripts,expected):
    return (isinstance(identity,dict) and type(identity.get('pid')) is int and identity['pid']>0
            and type(identity.get('create_time')) in {int,float}
            and Path(identity.get('script','')).resolve()==expected.resolve()
            and abs(float(identity['create_time'])-float(creation))<.01
            and any(Path(s).resolve()==expected.resolve() for s in scripts))

def probe(identity,expected):
    if not isinstance(identity,dict) or type(identity.get('pid')) is not int or identity['pid']<=0:
        return 'UNKNOWN_INVALID_OWNER_RECORD'
    try:
        process=psutil.Process(identity['pid'])
        scripts=[s for s in process.cmdline() if s.lower().endswith('.py')]
        return 'PRESENT_MATCHED_PID_AND_CREATE_TIME' if same_owner(identity,process.create_time(),scripts,expected) else 'ABSENT_OR_IDENTITY_CHANGED'
    except psutil.NoSuchProcess:
        return 'ABSENT_OR_IDENTITY_CHANGED'
    except (psutil.AccessDenied,ValueError,TypeError,OSError):
        return 'UNKNOWN_CANNOT_VERIFY_PROCESS'

def view_status(original):
    result=copy.deepcopy(original)
    result['live_process_check_at_utc']=datetime.now(timezone.utc).isoformat()
    selected=next(((version,base,script) for version,base,script in OWNERS if (R/f'launch_{base}.json').exists()),None)
    if selected is None:
        result['runner_liveness']='NO_ADMITTED_OWNER_RECORD'
        return result
    version,base,script=selected
    expected=R/'src'/script
    plan_path=R/f'launch_{base}.json'
    plan=json.loads(plan_path.read_text(encoding='utf-8'))
    result['runner_invocation_version']=version
    pins_valid=plan['launcher_sha256']==sha(expected) and plan['admission_sha256']==sha(R/f'admission_maven_{version}.json')
    completion=R/'runtime'/f'{base}_completion.json'
    if completion.exists():
        ended=json.loads(completion.read_text(encoding='utf-8'))
        if ended['launch_plan_sha256']==sha(plan_path) and pins_valid:
            result['runner_liveness']='INVOCATION_COMPLETION_RECORD_PRESENT'
            return result
    health=probe(plan.get('runner_identity'),expected) if pins_valid else 'UNKNOWN_OWNER_PLAN_PIN_DRIFT'
    result['runner_liveness']=health
    if health!='PRESENT_MATCHED_PID_AND_CREATE_TIME':
        result.update(snapshot_phase=original['phase'],phase='RUNNER_LIVENESS_REVIEW_REQUIRED',running=0,
                      active_sample_index=None,benchmark_admitted=False)
        result['blockers']=['Runner chưa được xác minh bằng owner PID/create-time/script và plan hash; kiểm tra trước job mới, không tự restart']+list(result.get('blockers',[]))
    return result
