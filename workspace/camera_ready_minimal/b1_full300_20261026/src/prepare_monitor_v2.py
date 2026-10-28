"""Version the read-only monitor for live job states; retain original source bytes."""
import json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
source=R/'monitor/serve.py';text=source.read_text(encoding='utf-8')
text=text.replace("R/'monitor/dist/index.html'","R/'monitor/dist_v2/index.html'")
text=text.replace("rows=json.loads((R/'manifest300.json').read_text(encoding='utf-8'))","manifest=R/'runtime/manifest_live300.json'\n    rows=json.loads((manifest if manifest.exists() else R/'manifest300.json').read_text(encoding='utf-8'))")
server=R/'monitor/serve_v2.py'
with server.open('x',encoding='utf-8') as f:f.write(text)
p=R/'monitor/dist/index.html';html=p.read_text(encoding='utf-8')
html=html.replace("NOT_STARTED:'Chưa bắt đầu'","NOT_STARTED:'Chưa bắt đầu',IN_PROGRESS:'Đang triển khai',RUNNING:'Đang chạy',COMPLETED_E1_MAVEN:'Hoàn tất E1 Maven',TERMINAL_PIPELINE_FAILURE:'Pipeline thất bại · giữ mẫu',INTERRUPTED_REVIEW_REQUIRED:'Dừng · cần kiểm tra',INCOMPLETE_REVIEW_REQUIRED:'Chưa hoàn tất · cần kiểm tra'")
html=html.replace('<option value="BLOCKED_GRADLE_QUALIFICATION">Gradle chờ tích hợp</option>','<option value="BLOCKED_GRADLE_QUALIFICATION">Gradle chờ tích hợp</option><option value="RUNNING">Đang chạy</option><option value="COMPLETED_E1_MAVEN">Hoàn tất E1 Maven</option><option value="TERMINAL_PIPELINE_FAILURE">Pipeline thất bại</option><option value="INTERRUPTED_REVIEW_REQUIRED">Dừng để kiểm tra</option>')
html=html.replace('Độ phủ bằng chứng E1','Trạng thái cohort E1')
html=html.replace("text('evo',`Lượt EvoSuite mới: ${s.new_EvoSuite_calls}`)","text('evo',`EvoSuite: ${s.benchmark_EvoSuite_calls||0} lượt benchmark · ${s.fixture_EvoSuite_calls||0} lượt fixture`)")
html=html.replace('Class mới hoàn tất / 251','Class mới có kết quả / 251')
html=html.replace('49 class cũ đã được xác minh; E1-full300 chưa được dùng để kết luận non-inferiority.','49 class cũ đã được xác minh. Class mới có kết quả có thể thành công hoặc thất bại; không đồng nghĩa đủ suite evidence. Chưa có kết luận E1-full300.')
html=html.replace("s.benchmark_admitted?'Đã qua cổng':'CHƯA'","s.benchmark_admitted?'Maven được admit · Gradle chưa':'CHƯA'")
dest=R/'monitor/dist_v2/index.html';dest.parent.mkdir(exist_ok=True)
with dest.open('x',encoding='utf-8') as f:f.write(html)
record={'prior_server_sha256':audit.sha(source),'prior_html_sha256':audit.sha(p),'new_server_sha256':audit.sha(server),'new_html_sha256':audit.sha(dest),'port':8766,'routes_unchanged':True,'public_manifest_fields_unchanged':True,'new_job_control_routes':False}
with (R/'audit/monitor_v2_registry.json').open('x',encoding='utf-8') as f:json.dump(record,f,indent=2)
audit.log('B1_MONITOR_V2_PREPARED',**record);print(json.dumps(record,indent=2))
