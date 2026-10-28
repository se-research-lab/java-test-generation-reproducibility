"""RQ5 Maven-only sensitivity from frozen historical rows; no experiment calls."""
import csv,json,sys
from collections import Counter
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
source=BASE/'backup/original/scripts_v2/results/runs/full300_merged_20260724_paper/metrics_wide.csv'
with source.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
assert audit.sha(source)==audit.sha(audit.RUN/'metrics_wide.csv')
out=BASE/'outputs/maven260_sensitivity';out.mkdir(exist_ok=False)
summary=[]
for label,subset in [('all300',rows),('Maven260',[r for r in rows if r['build_tool']=='Maven']),('Gradle40',[r for r in rows if r['build_tool']=='Gradle'])]:
    n=len(subset);g=sum(r['gpt_compilation']=='1' for r in subset);e=sum(r['evosuite_compilation']=='1' for r in subset)
    c=Counter((int(r['gpt_compilation']),int(r['evosuite_compilation'])) for r in subset)
    summary.append({'population':label,'n':n,'repositories':len({r['repo_id'] for r in subset}),
      'GPT_builds':g,'E0_builds':e,'GPT_percent':100*g/n,'E0_percent':100*e/n,
      'difference_GPT_minus_E0_pp':100*(g-e)/n,'both_build':c[1,1],'GPT_only':c[1,0],
      'E0_only':c[0,1],'neither_build':c[0,0]})
assert [(r['n'],r['GPT_builds'],r['E0_builds']) for r in summary]==[(300,61,158),(260,51,158),(40,10,0)]
with (out/'buildability_table.csv').open('x',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
with (out/'maven260_keys.csv').open('x',encoding='utf-8',newline='') as f:
    w=csv.writer(f);w.writerow(['class_key']);w.writerows([r['class_key']] for r in rows if r['build_tool']=='Maven')
report={'status':'PASS','source_sha256':audit.sha(source),'scope':'post-review descriptive sensitivity of historical E0/G0 process-build flags',
    'table':summary,'no_new_generation':True,'no_new_hypothesis_test':True,
    'RQ3_primary_preserved':'61/300; Maven51/260 is RQ5 sensitivity only',
    'limitations':['E0 assertions-off','legacy process gate not all-tests-pass certification','Maven260 sensitivity is not a Gradle harness repair','does not establish E1 full300 buildability']}
with (out/'summary.json').open('x',encoding='utf-8') as f:json.dump(report,f,indent=2);f.write('\n')
text='''# RQ5 sensitivity trên 260 class Maven

Đây là phân tích dữ liệu lịch sử G0/E0, không chạy lại Java hoặc gọi GPT. E0 vẫn là cấu hình tắt assertions; build success theo gate của pipeline đã dùng.

| Mẫu | GPT build | E0 build | Chênh lệch GPT−E0 |
| --- | ---: | ---: | ---: |
| Toàn300 | 61/300 = 20,33% | 158/300 = 52,67% | −32,33pp |
| Maven260 | 51/260 = 19,62% | 158/260 = 60,77% | −41,15pp |
| Gradle40 | 10/40 = 25,00% | 0/40 = 0,00% | +25,00pp |

Trong Maven260: cả hai build49, chỉ GPT2, chỉ E0109, cả hai không build100. Loại40 Gradle thất bại ở E0 làm lợi thế buildability của E0 trên Maven lớn hơn, không giải thích hết chênh lệch theo hướng bất lợi cho E0. Kết luận vẫn thuộc pipeline Maven đã đánh giá, chưa phải thuộc tính tổng quát của generator.

Phân tích này trực tiếp đáp ứng lựa chọn Maven-only sensitivity mà R2.2 cho phép; không cần sửa harness Gradle để làm phép tính này. Nó không thay thế R2.1 rerun EvoSuite assertions-enabled.

RQ3 primary vẫn61/300. Không thay bằng51/260. Không dùng260 class để diễn giải mutation quality của49 cặp. Chưa thêm p-value, CI hay quyết định NI mới.

English insertion proposal:

As a build-tool sensitivity analysis, we restricted the historical comparison to the 260 Maven classes. GPT-4o-mini and EvoSuite produced process-build successes for 51/260 (19.62%) and 158/260 (60.77%) classes, respectively, a paired rate difference of −41.15 percentage points. The paired counts were 49 joint successes, 2 GPT-only successes, 109 EvoSuite-only successes, and 100 joint failures. Thus, excluding the 40 Gradle classes did not remove the observed Maven pipeline buildability advantage for EvoSuite. These results refer to the evaluated historical pipelines and their build gate; the primary GPT replication estimate remains 61/300 (20.33%).
'''
(out/'BAO_CAO_MAVEN260.md').write_text(text,encoding='utf-8')
# Dedicated completion record avoids concurrent writes to the shared ledger during cache copy.
with (out/'completion_record.json').open('x',encoding='utf-8') as f:json.dump({'kind':'MAVEN260_ANALYTICS_COMPLETE','summary_sha256':audit.sha(out/'summary.json'),'no_original_data_changed':True},f,indent=2)
print(json.dumps(report,indent=2))
