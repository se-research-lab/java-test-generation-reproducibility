from pathlib import Path
from collections import Counter
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / 'scripts_v2/results/runs/full300_merged_20260724_paper'
OUT = Path(__file__).resolve().parent
rows = pd.read_csv(RUN/'metrics_long.csv')
api = pd.read_csv(RUN/'api_log.csv')
phase = pd.read_csv(RUN/'phase_log.csv')
gradle=[]
for row in rows[(rows.arm=='evosuite')&(rows.build_tool=='Gradle')].itertuples():
    paths=list((RUN/'class_logs'/row.source_run_id).glob(f'{int(row.source_run_sample_index):03d}_*.stdout.log'))
    assert len(paths)==1
    lines=paths[0].read_text(encoding='utf-8',errors='replace').splitlines()
    match=[(i+1,x) for i,x in enumerate(lines) if 'trying to move the scaffolding file' in x or "local variable 'project_df_evosuite' referenced before assignment" in x]
    gradle.append(dict(class_key=row.class_key,log=str(paths[0]),signatures=match,
        classification='missing_scaffolding' if any('trying to move' in x[1] for x in match) else 'uninitialized_dataframe' if match else 'other'))
warnings=phase[phase.astype(str).apply(lambda s:s.str.contains('pit_report_missing|jacoco_report_missing',regex=True)).any(axis=1)]
retries=phase[phase.detail.astype(str).str.contains('sanitized retry',regex=False)]
summary=dict(gradle_failure_signatures=dict(Counter(x['classification'] for x in gradle)),
    gradle_details=gradle,
    api_summary=api[['duration_sec','prompt_tokens','completion_tokens','total_tokens','attempts']].describe().to_dict(),
    api_totals=api[['duration_sec','prompt_tokens','completion_tokens','total_tokens']].sum().to_dict(),
    api_timestamps_by_run=api.groupby('source_run_id').timestamp_utc.agg(['min','max']).to_dict(orient='index'),
    evosuite_sanitized_retries={'event_rows':len(retries),'unique_class_keys':int(retries.class_key.nunique()),
        'outcomes':retries.status.value_counts().to_dict(),
        'events':retries[['class_key','source_run_id','status']].fillna('').to_dict(orient='records')},
    missing_report_warnings=warnings.fillna('').to_dict(orient='records'),
    measurement_failure_flags=rows[rows.fail_stage.isin(['jacoco_failed','pit_failed'])][['class_key','arm','compilation','fail_stage']].to_dict(orient='records'))
(OUT/'diagnostics.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
print(json.dumps({k:v for k,v in summary.items() if k not in ['gradle_details','missing_report_warnings','measurement_failure_flags']},indent=2))
print('MISSING REPORT WARNING COUNT',len(warnings))
print(warnings.to_string(index=False)[:6000])
row=rows[(rows.arm=='gpt')&(rows.fail_stage=='jacoco_failed')].iloc[0]
p=next((RUN/'class_logs'/row.source_run_id).glob(f'{int(row.source_run_sample_index):03d}_*.stdout.log'))
print('JACOCO SAMPLE',str(p))
lines=p.read_text(encoding='utf-8',errors='replace').splitlines()
print('\n'.join(x for x in lines if any(k in x.lower() for k in ['error','jacoco','tests run','build','fail']))[-5500:])
