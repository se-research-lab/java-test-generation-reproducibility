"""Resume after parent-directory preparation failed before any slot or generation began.
Frozen execution functions, protocol, schedule and admission are retained unchanged.
"""
import json,os,sys
from pathlib import Path
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));sys.path.insert(0,str(B/'src'))
import audit,repeat_subset_driver_v1 as d
from dotenv import dotenv_values
from openai import OpenAI
ST=d.ST;d.verify_core();auth=d.load(ST/'explicit_payload_authorization_v1.json');assert auth['payload_file_sha256']==audit.sha(ST/'prompts15.json')
assert not (ST/'slots').exists() and not (ST/'api_attempts.jsonl').exists()
events=[json.loads(l) for l in (ST/'events.jsonl').read_text(encoding='utf-8').splitlines()]
assert not any(r['kind'] in ['SLOT_START','API_POST_START','SLOT_MEASURED','SLOT_COMPLETE'] for r in events)
assert d.load(ST/'batch_admission.json')['slots']==150
amendment={'reason':'Create omitted slots parent after FileNotFoundError before any slot/source copy/API/generation/measurement. No frozen function or experimental configuration changed.','frozen_driver_sha256':audit.sha(B/'src/repeat_subset_driver_v1.py'),'controller_sha256':audit.sha(__file__),'prior_admission_sha256':audit.sha(ST/'batch_admission.json'),'prior_generation_calls':0,'prior_measurement_calls':0,'prior_API_POST_calls':0,'explicit_authorization_sha256':audit.sha(ST/'explicit_payload_authorization_v1.json')}
d.dump(ST/'parent_directory_recovery_v1.json',amendment);audit.log('REPEAT15_PRE_SLOT_PARENT_RECOVERY',**amendment)
(ST/'slots').mkdir()
key=dotenv_values(audit.ROOT/'scripts_v2/.env').get('OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY');assert key
client=OpenAI(api_key=key,max_retries=0,timeout=120,base_url='https://api.openai.com/v1');budget=d.Budget();jobs={j['class_key']:j for j in d.load(ST/'input_jobs15.json')};results=[]
for slot in d.load(ST/'schedule150.json'):
    d.verify_core()
    try:r=d.execute(slot,jobs[slot['class_key']],budget,client)
    except BaseException as exc:
        d.event('BATCH_ABORT',controller='v2',exception_class=type(exc).__name__,detail=str(exc)[:800] if isinstance(exc,AssertionError) else 'Preserved logs; no automatic rerun of started slots');raise
    results.append(r);print(json.dumps({'completed':len(results),'n':150,'slot_id':slot['slot_id'],'job':slot['job_index'],'replicate':slot['replicate'],'arm':slot['arm'],'build':r['legacy_process_build'],'score':r['legacy_strict_mutation_percent']}),flush=True)
d.dump(ST/'results150.json',results);d.frozen.check_gpt();audit.verify();d.dump(ST/'complete.json',{'status':'COMPLETE','n':150,'results_sha256':audit.sha(ST/'results150.json'),'GPT_slots':75,'EvoSuite_slots':75,'finished_utc':d.now(),'reserved_estimated_GPT_USD':budget.reserved});d.event('BATCH_COMPLETE',n=150,results_sha256=audit.sha(ST/'results150.json'))
