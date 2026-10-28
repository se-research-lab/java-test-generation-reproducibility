import json,sys
from pathlib import Path
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
S=B/'repeated_subset_v1';r=json.loads((S/'STOP_DO_NOT_RESUME.json').read_text());audit.log('AUTHOR_REVOKED_REPEATED_GENERATION',stop_report=r,stop_report_sha256=audit.sha(S/'STOP_DO_NOT_RESUME.json'),snapshot_sha256=audit.sha(S/'stop_snapshot_manifest_v1.json'),note='v1 stop files completed; final audit event recovered without modifying any evidence')
print(json.dumps(r,indent=2))
