"""Complete historical failure-stage/owner tables; no rerun or relabeling."""
import csv,json,sys
from collections import Counter
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
source=BASE/'backup/original/scripts_v2/results/runs/full300_merged_20260724_paper/metrics_long.csv'
assert audit.sha(source)==audit.sha(audit.RUN/'metrics_long.csv')
with source.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
assert len(rows)==600
out=BASE/'outputs/failure_stage_complete';out.mkdir(exist_ok=False)
arms=['gpt','evosuite'];summary={}
for key in ['fail_stage','failure_owner']:
    table=[]
    values=sorted({r[key] for r in rows},key=lambda x:(x!='ok',x))
    for value in values:
        rec={key:value}
        for arm in arms:
            sub=[r for r in rows if r['arm']==arm];assert len(sub)==300
            n=sum(r[key]==value for r in sub);rec[arm+'_n']=n;rec[arm+'_percent']=round(100*n/300,2)
        table.append(rec)
    assert all(sum(r[a+'_n'] for r in table)==300 for a in arms)
    with (out/(key+'_table.csv')).open('x',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    summary[key]=table
noncalls=[r for r in rows if r['arm']=='gpt' and r['fail_stage']=='maven_reactor_prewarm_failed'];assert len(noncalls)==2
with (out/'no_GPT_call_rows.csv').open('x',encoding='utf-8-sig',newline='') as f:
    fields=['class_key','source_run_id','source_run_sample_index','fail_stage','failure_owner','failure_detail'];w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(noncalls)
summary.update(source_sha256=audit.sha(source),stage_labels_preserved=True,no_new_generation=True,GPT_no_call_records=2,
 interpretation='Recorded pipeline taxonomy, not validated causal blame; ok means legacy process gate, not all assertions pass')
with (out/'summary.json').open('x',encoding='utf-8') as f:json.dump(summary,f,indent=2)
md=['# Bảng failure-stage đầy đủ cho main text','', 'Dữ liệu lịch sử G0/E0, mỗi nhánh300class. Giữ nguyên labels; đây là phân loại pipeline đã lưu, không phải kết luận nguyên nhân đã chứng minh. ok theo legacy gate, chưa đồng nghĩa mọi test pass.','','| Stage | GPT n (%) | E0 n (%) |','| --- | ---: | ---: |']
for r in summary['fail_stage']:md.append('| '+r['fail_stage']+' | '+str(r['gpt_n'])+' ('+str(r['gpt_percent'])+'%) | '+str(r['evosuite_n'])+' ('+str(r['evosuite_percent'])+'%) |')
md+=['','Hai GPT rows bị chặn ở preprocessing/prewarm không có API call; vẫn ở denominator300. Không gọi chúng là model-generation failures. Các labels agonetest_harness/generator_output là taxonomy vận hành, không chứng minh generator là nguyên nhân duy nhất.','', 'Bảng này đóng yêu cầu R2 minor về complete failure-stage table; không cần chạy lại49 hoặc300class.']
(out/'BAO_CAO_FAILURE_STAGES.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
audit.log('HISTORICAL_FAILURE_TABLE_COMPLETE',summary_sha256=audit.sha(out/'summary.json'),rows=600,relabeled_rows=0)
print(json.dumps(summary,indent=2))
