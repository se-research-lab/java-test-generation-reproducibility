import json,sys
from datetime import datetime,timezone
from pathlib import Path
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
obj={'recorded_utc':datetime.now(timezone.utc).isoformat(),'authorization_source':'Explicit user reply in this conversation after auto-review rejection','user_reply':'Đồng ý gửi các payload này để hoàn thành repeated subset','payload_file':'repeated_subset_v1/prompts15.json','payload_file_sha256':audit.sha(B/'repeated_subset_v1/prompts15.json'),'destination':'https://api.openai.com/v1/chat/completions','model':'gpt-4o-mini-2024-07-18','planned_generation_realizations':75,'max_attempts_per_slot':5,'estimated_cost_cap_USD':2.0,'payload_transmission_inventory_sha256':audit.sha(B/'repeated_subset_v1/payload_transmission_inventory.json'),'prior_auto_review_rejection_preserved':True}
p=B/'repeated_subset_v1/explicit_payload_authorization_v1.json'
with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2);f.write('\n')
audit.log('EXPLICIT_REPEAT_PAYLOAD_AUTHORIZATION',path=str(p.relative_to(B)),sha256=audit.sha(p),payload_file_sha256=obj['payload_file_sha256'],destination=obj['destination'],planned_generations=75,max_attempts_per_slot=5,estimated_cost_cap_USD=2.0)
audit.log('NEW_FILE_REGISTERED',path=str(Path(__file__).relative_to(B)),sha256=audit.sha(__file__),bytes=Path(__file__).stat().st_size,change_type='record explicit user approval after automatic review rejected external payload transmission')
print(json.dumps({'status':'AUTHORIZATION_RECORDED','payload_file_sha256':obj['payload_file_sha256']},indent=2))
