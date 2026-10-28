"""Read-only E49 status: no benchmark run, no file writes, no scores aggregated."""
import json
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];STAGE=BASE/'e49_driver'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def last(p):
    lines=p.read_text(encoding='utf-8').splitlines() if p.exists() else []
    return json.loads(lines[-1]) if lines else None
completed=[]
for i in range(1,50):
    p=STAGE/('job_result_%02d.json'%i)
    if p.exists():
        try:r=read(p)
        except json.JSONDecodeError:continue
        completed.append(i)
result={'completed_jobs':len(completed),'scheduled_jobs':49,'exact_indices_completed':completed,
    'benchmark_last_event':last(STAGE/'resume_guard02/events.jsonl'),
    'archive_complete':read(STAGE/'archive_final_v4/summary.json')['all49_complete'] if (STAGE/'archive_final_v4/summary.json').exists() else False,
    'postrun_last_event':last(STAGE/'postrun_v1/events.jsonl'),
    'analysis_report_exists':(BASE/'outputs/e49_final_v1/BAO_CAO_E49.md').exists(),
    'GPT_source_outputs_updated':False,'note':'status only; verify frozen guard/audit for data-integrity certification'}
try:
    import psutil
    active=[]
    for p in psutil.process_iter(['pid','name','cmdline']):
        try:
            args=p.info.get('cmdline') or []
            if p.info.get('name','').lower()=='python.exe' and any(Path(a).name in ['resume_e49_after_process_interruption.py','archive_e49_final_v4.py','wait_e49_then_analyze_v1.py'] for a in args):active.append({'pid':p.info['pid'],'scripts':[Path(a).name for a in args if a.endswith('.py')]})
        except(psutil.NoSuchProcess,psutil.AccessDenied):pass
    result['active_owned_python_processes']=active
except ImportError:result['process_check']='psutil unavailable'
print(json.dumps(result,ensure_ascii=False,indent=2))
