"""Correct the counter expectation from raw plans without altering any result."""
import sys
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
source=R/'src/reconcile_projection_failure_v1.py';target=R/'src/reconcile_projection_failure_v2.py'
text=source.read_text(encoding='utf-8').replace("O=R/'audit/projection_reconciliation_v1'","O=R/'audit/projection_reconciliation_v2'")
text=text.replace("started==11 and planned==13 and not_started==[12,16]","started==11 and planned==14 and not_started==[12,16,23]")
text=text.replace("'spawn_failures_before_start':[12,16]","'spawn_failures_before_start':not_started")
with target.open('x',encoding='utf-8') as f:f.write(text)
compile(text,str(target),'exec')
record={'prior_script_sha256':sha(source),'new_script_sha256':sha(target),'reason':'Raw command plans show14 planned /11 started; Win206 before start in012,016,023; class019 had two actual technical attempts','prior_preflight_no_UI_outputs':not (R/'audit/projection_reconciliation_v1').exists(),'raw_results_modified':False,'new_processes':0}
dump(R/'audit/projection_counter_correction_v2.json',record);audit.log('B1_PROJECTION_COUNTER_CORRECTION_PREPARED',**record);print('Prepared reconciliation v2 from actual14plans/11starts; old source and raw evidence preserved')
