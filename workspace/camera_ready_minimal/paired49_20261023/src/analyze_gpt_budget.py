"""Read-only GPT budget accounting from frozen merged API log; no API access."""
import csv,json,statistics,sys
from collections import Counter
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
source=audit.RUN/'api_log.csv';h=audit.sha(source)
def readcsv(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
rows=readcsv(source);paired=readcsv(BASE/'outputs/paired49.csv');keys={r['class_key'] for r in paired}
assert len(rows)==298 and len({r['class_key'] for r in rows})==298
selected=[r for r in rows if r['class_key'] in keys];assert len(selected)==49
out=BASE/'outputs/budget_accounting';out.mkdir(exist_ok=False)
def stats(rs):
    data={'recorded_API_rows':len(rs),'status_counts':dict(Counter(r['status'] for r in rs)),'attempt_counts':dict(Counter(r['attempts'] for r in rs)),'requested_model':dict(Counter(r['model_requested'] for r in rs)),'returned_model':dict(Counter(r['model_returned'] for r in rs)),'token_cap_counts':dict(Counter(r['max_tokens'] for r in rs))}
    for k in ['duration_sec','prompt_tokens','completion_tokens','total_tokens']:
        v=[float(r[k]) for r in rs if r[k]!=''];data[k]={'available':len(v),'sum':sum(v),'mean':statistics.mean(v),'median':statistics.median(v),'min':min(v),'max':max(v)}
    return data
report={'source':str(source),'source_sha256':h,'all300_G0_API_log':stats(rows),'fixed49_G0_API_log':stats(selected),'no_API_rows':2,'generation_calls_now':0,
    'limits':['API duration is not full pipeline time; does not measure hidden inference compute','EvoSuite search60s is an algorithm budget; generation command includes overhead and assertion generation','240s command cap/max2 conditional attempts are not equal compute to one API call','Do not infer equal costs/wall time or select seeds/classes by performance']}
with (out/'gpt_api_budget.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
fields=['class_key','duration_sec','prompt_tokens','completion_tokens','total_tokens','attempts','status','max_tokens','source_run_id']
with (out/'fixed49_gpt_api_budget.csv').open('x',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(selected)
s=report['fixed49_G0_API_log'];allstats=report['all300_G0_API_log']
text=f'''# Budget và phạm vi tính công bằng

Đọc lại API log G0 archived, không gọi API. Log gộp có298 rows trên300 class;2 class bị chặn trước generation. Fixed49 có49 API rows, không đổi cohort.

| Log API latency/token usage | Toàn298 API rows | Fixed49 |
|---|---:|---:|
|Median API duration (s)|{allstats['duration_sec']['median']:.3f}|{s['duration_sec']['median']:.3f}|
|Mean API duration (s)|{allstats['duration_sec']['mean']:.3f}|{s['duration_sec']['mean']:.3f}|
|Median completion tokens|{allstats['completion_tokens']['median']:.1f}|{s['completion_tokens']['median']:.1f}|
|Mean completion tokens|{allstats['completion_tokens']['mean']:.1f}|{s['completion_tokens']['mean']:.1f}|

Model/snapshot, token caps, attempts và trạng thái đầy đủ trong JSON/CSV; không suy one-call chỉ từ số file nếu log attempts khác1.

E1 giữ search_budget60, cap240s mỗi generation command, tối đa2 attempts theo conditional sanitized retry có sẵn. Assertion MUTATION/scaffold/runtime được bật. API latency và search budget đo hai cơ chế khác nhau; không tuyên bố equal compute. Thời gian compile/PIT/JaCoCo không phải generation latency. Token cap2048 là giới hạn đầu ra, không tương đương60s CPU search. Chưa có năng lượng/hardware-normalized compute hoặc billing/cost comparison đáng tin cậy.

Phản hồi R3.2 tối thiểu: báo budgets và overhead riêng, nêu giới hạn; không đổi GPT call/token budget hay search objective giữa batch. Khi đủ49, command JSON cho phép tách generation wall time, attempts/timeouts và measurement time. Không dùng khác biệt thời gian để tự tăng budget của công cụ đang kém điểm.
'''
with (out/'BAO_CAO_BUDGET.md').open('x',encoding='utf-8') as f:f.write(text)
assert audit.sha(source)==h
audit.log('G0_BUDGET_READONLY_ANALYSIS',API_rows=298,fixed49_API_rows=49,source_sha256=h,new_API_calls=0)
print(json.dumps({'status':'PASS','API_rows_read':298,'fixed49_rows':49,'new_API_calls':0}))
