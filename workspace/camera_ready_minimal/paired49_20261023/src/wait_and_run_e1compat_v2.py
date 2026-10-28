"""Sequential guard-controlled diagnostic queue; never performs generation or API calls."""
import json,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
STAGE=BASE/'e1_compatibility_diagnostic_v1'
def dump(p,x):
    with p.open('x',encoding='utf-8') as f:json.dump(x,f,ensure_ascii=False,indent=2);f.write('\n')
def main():
    out=STAGE/'diagnostic_queue_v2';out.mkdir(exist_ok=False)
    scripts={
        'src/diagnose_e1_compatibility_v4.py':'82ad00778ff7cb423f16051ede46d316238dbf45b354e90d9216ca20a9517ed9',
        'src/run_e1compat_junit_v2.py':'054933cbf7546d48ffc525116e1728aea76fd9c88e606f1828fe94b80e16f5fa',
        'src/replay_e1_discovery_runtime_v2.py':'a8a80c71c4042cb34e3fef27ed6abc283715ccd48bf208f8b10544599c12b386',
        'src/run_e1compat_guarded_v2.py':'380c8f84e08c6751128b1b204bcc6f080c6a156093072935daf6f94d55859867',
    }
    for rel,h in scripts.items():assert audit.sha(BASE/rel)==h,rel
    steps=[]
    for job in ['09','12','13','14','15']:steps.append(('junit_'+job,['run_e1compat_junit_v2.py',job]))
    for job in ['18','19']:steps.append(('collect_'+job,['replay_e1_discovery_runtime_v2.py','collect',job]))
    for job in ['18','19']:steps.append(('direct_'+job,['replay_e1_discovery_runtime_v2.py','hazel_direct',job]))
    for method in [None,'test0','test1','test2']:steps.append(('runtime48_'+(method or 'full'),['replay_e1_discovery_runtime_v2.py','runtime48']+([method] if method else [])))
    admission={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'waiting_for':'input_lock.json','supersedes_stopped_queue_v1':'semantic XML whitespace guard stopped before POM write/test; all prior logs retained','scripts':scripts,'steps':steps,'GPT_API_calls':0,'generation_calls':0,'E1_scores_replaced':False,'fail_stop_on_guard_or_execution_error':True}
    dump(out/'admission.json',admission);audit.log('E1_COMPATIBILITY_QUEUE_ADMITTED',sha256=audit.sha(out/'admission.json'),steps=len(steps),no_generation=True,no_GPT=True)
    deadline=time.monotonic()+2700
    while not (STAGE/'input_lock.json').exists():
        if time.monotonic()>deadline:raise TimeoutError('Preparation input lock not available')
        time.sleep(1)
    # File is written exclusively after all input copies; retry only while final JSON write is incomplete.
    for attempt in range(10):
        try:json.loads((STAGE/'input_lock.json').read_text(encoding='utf-8'));break
        except json.JSONDecodeError:time.sleep(.2)
    else:raise AssertionError('Incomplete input lock')
    results=[]
    for name,args in steps:
        for rel,h in scripts.items():assert audit.sha(BASE/rel)==h,rel
        argv=[sys.executable,'-B','-X','utf8',str(BASE/'src/run_e1compat_guarded_v2.py'),*args]
        label='e1compat_'+name+'_v2'
        started=datetime.now(timezone.utc).isoformat()
        audit.log('E1_COMPATIBILITY_QUEUE_STEP',name=name,status='START',argv=argv)
        try:audit.run(label,argv)
        except BaseException:
            dump(out/'stopped.json',{'step':name,'timestamp_utc':datetime.now(timezone.utc).isoformat(),'prior_completed_steps':results,'no_results_replaced':True})
            audit.log('E1_COMPATIBILITY_QUEUE_STOPPED',name=name,report_sha256=audit.sha(out/'stopped.json'))
            raise
        result={'step':name,'started_utc':started,'completed_utc':datetime.now(timezone.utc).isoformat()};results.append(result)
        print('DIAGNOSTIC STEP COMPLETE '+name,flush=True)
    dump(out/'complete.json',{'status':'COMPLETE','steps':results,'GPT_API_calls':0,'generation_calls':0,'E1_scores_replaced':False})
    audit.log('E1_COMPATIBILITY_QUEUE_COMPLETE',sha256=audit.sha(out/'complete.json'),steps=len(results))
if __name__=='__main__':main()
