import sys,json,hashlib
from pathlib import Path
from datetime import datetime,timezone
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B));import audit
S=B/'repeated_subset_v1'; now=datetime.now(timezone.utc).isoformat()
rows=[json.loads(x) for x in (S/'events.jsonl').read_text(encoding='utf-8').splitlines() if x.strip()]
starts=[r for r in rows if r['kind']=='API_POST_START']; ends=[r for r in rows if r['kind']=='API_POST_END']; ok=[r for r in ends if r.get('status')=='OK']
usage={k:sum(r.get('usage',{}).get(k,0) for r in ok) for k in ['prompt_tokens','completion_tokens','total_tokens']}
cost=usage['prompt_tokens']*.15/1e6+usage['completion_tokens']*.60/1e6
report={'status':'STOPPED_BY_AUTHOR_DO_NOT_RESUME','timestamp_utc':now,'new_generation_authorization_revoked':True,'no_active_python_java_processes_at_stop_inspection':True,'last_batch_state':'ABORTED slot010 ParseError; existing response retained','API_requests_started':len(starts),'API_requests_ended':len(ends),'successful_responses':len(ok),'usage':usage,'estimated_usage_cost_USD':cost,'cost_note':'Estimate from recorded usage and nominal uncached rates, not billing confirmation; all attempts retained.','paper_use_of_any_repeated_data':False,'new_API_EvoSuite_E300_Gradle_jobs_permitted':False,'automatic_resume_permitted':False,'files_deleted':0}
for name,obj in [('STOP_DO_NOT_RESUME.json',report),('stop_snapshot_manifest_v1.json',{'files':[{'path':p.relative_to(S).as_posix(),'bytes':p.stat().st_size,'sha256':audit.sha(p)} for p in sorted(S.rglob('*')) if p.is_file()]})]:
 p=S/name
 with p.open('x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2)
 audit.log('REPEATED_STOP_EVIDENCE',path=p.relative_to(B).as_posix(),sha256=audit.sha(p))
audit.log('AUTHOR_REVOKED_REPEATED_GENERATION',**report)
print(json.dumps(report,indent=2))
