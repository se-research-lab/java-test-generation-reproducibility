import sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE))
import audit
for name in ['src/analyze_measurement_compat49_v2.py','src/independent_measurement49_raw_audit_v2.py']:
    p=BASE/name
    audit.log('FILE_CREATED',path=str(p),sha256=audit.sha(p),reason='Inspection-only annotation inventory and immutable lock extension support; original v1 preserved; no score/gate/cohort changes')
print('Two analysis v2 source creations audited; no experiment calls')
