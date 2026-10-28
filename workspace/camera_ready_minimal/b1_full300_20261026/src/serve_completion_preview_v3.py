"""Read-only loopback view of completion receipts; cannot launch any experiment."""
import json,sys
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlsplit
from datetime import datetime,timezone
import psutil
from maven_adapter_v1 import R
A=R/'completion_amendment_v1';PORT=8767
HTML='''<!doctype html><html lang="vi"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>E1 completion audit</title><style>body{font:15px system-ui;margin:28px auto;max-width:1120px;background:#f6f8fc;color:#18233a;padding:0 18px}h1{font-size:25px}.cards{display:flex;gap:12px;flex-wrap:wrap}.card{background:white;border:1px solid #d7dfec;padding:16px;border-radius:10px;min-width:150px}.n{font-size:30px;font-weight:700}table{border-collapse:collapse;width:100%;background:white;margin:20px 0}td,th{border-bottom:1px solid #dae0e9;padding:9px;text-align:left}.note{background:#fff3d4;padding:14px;border-radius:8px}small{color:#52627a}pre{white-space:pre-wrap}</style><h1>E1 — bổ sung sau quan sát lỗi</h1><p class="note">Tập so sánh cố định 300 class. GPT/E0 giữ nguyên. Test-only gate không phải gate verify+PIT. Còn unresolved thì chưa gọi E1-full300 hoàn chỉnh.</p><div id="health"></div><div id="cards" class="cards"></div><h2>Các nhóm được khóa</h2><table><thead><tr><th>Nhóm</th><th>Có result mới</th><th>Unresolved receipt</th><th>Generation mới</th><th>Phạm vi</th></tr></thead><tbody id="groups"></tbody></table><h2>Kết quả mới</h2><table><thead><tr><th>Index</th><th>Nhóm</th><th>Test XML</th><th>PIT report</th><th>Observed %</th><th>Gate/ghi chú</th></tr></thead><tbody id="results"></tbody></table><small id="stamp"></small><script>async function refresh(){try{let s=await(await fetch('/status.json',{cache:'no-store'})).json();document.querySelector('#health').textContent=s.health;document.querySelector('#cards').innerHTML=[['Slots',300],['Result mới',s.results.length],['GPT/API mới',0],['Generation mới',s.generation_calls]].map(x=>'<div class="card">'+x[0]+'<div class="n">'+x[1]+'</div></div>').join('');document.querySelector('#groups').innerHTML=s.groups.map(g=>'<tr><td>'+g.group+'</td><td>'+g.results+'</td><td>'+g.unresolved+'</td><td>'+g.generations+'</td><td>'+g.scope+'</td></tr>').join('');document.querySelector('#results').innerHTML=s.results.map(r=>'<tr><td>'+r.index+'</td><td>'+r.group+'</td><td>'+r.test+'</td><td>'+r.pit+'</td><td>'+(r.score===null?'—':r.score)+'</td><td>'+r.gate+'</td></tr>').join('');document.querySelector('#stamp').textContent='Cập nhật '+s.at_utc+' | '+s.progress;}catch(e){document.querySelector('#health').textContent='Snapshot chưa đọc được; giữ dữ liệu hiển thị trước.'}}refresh();setInterval(refresh,10000)</script></html>'''
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def snapshot():
 groups=[];results=[];calls=0
 for group,version in [('pit','v2'),('junit3','v2'),('pom','v2')]:
  folders=list((R/'jobs').glob('*_completion_'+group+'_'+version));generated=0;unresolved=0;count=0
  if group=='pom':folders+=list((R/'jobs').glob('*_completion_pom_v1'))+list((R/'jobs').glob('*_completion_pom_v3'))+list((R/'jobs').glob('*_completion_pom_resume_after173_v1'))
  selected={}
  for folder in sorted(folders):
   for p in (folder/'commands').glob('*/plan.json'):
    if (p.parent/'started.json').exists() and '-jar' in load(p)['argv']:generated+=1
   unresolved+=int((folder/'unresolved.json').exists())
   p=folder/'result.json'
   if not p.exists():continue
   d=load(p);selected[d['sample_index_1based']]=d
  if group=='pom' and (A/'result_reconciliations_v1/112/result.json').exists():selected[112]=load(A/'result_reconciliations_v1/112/result.json')
  for i,d in selected.items():
   test='pass' if d.get('strict_suite_evidence') else 'xem flags';pit=('partial/timeout — rejected' if d.get('PIT_report_complete') is False and d.get('pit_report_present') else 'có' if d.get('pit_report_present') else 'chưa có')
   results.append({'index':i,'group':group,'test':test,'pit':pit,'score':d.get('observed_mutation_percent',d.get('mutation_score_percent')),'gate':'test-only; PIT unresolved' if d.get('test_only_process_gate') is not None else str(d.get('legacy_process_build'))});count+=1
  calls+=generated;groups.append({'group':group,'results':count,'unresolved':unresolved,'generations':generated,'scope':'suite cũ; measurement' if group=='pit' else 'suite cũ; compile/test, PIT unresolved' if group=='junit3' else 'resume211/220/269/275/294; 25 checkpoint giữ nguyên'})
 active=[]
 for name in ['maven_junit3_run_v2','maven_pom_run_v2','maven_pom_run_v3','maven_pom_resume_after173_v1','gradle_pit_run_v2']:
  p=A/name/'owner.json'
  if not p.exists():continue
  d=load(p)
  try:
   process=psutil.Process(d['pid'])
   if process.create_time()==d['create_time']:active.append(name)
  except psutil.NoSuchProcess:pass
 progress=load(R/'runtime/completion_progress.json') if (R/'runtime/completion_progress.json').exists() else {}
 return {'at_utc':datetime.now(timezone.utc).isoformat(),'health':'Worker đang chạy: '+', '.join(active) if active else 'Không thấy worker benchmark đang sống; xem completion/interruption receipts.','groups':groups,'results':sorted(results,key=lambda r:r['index']),'generation_calls':calls,'progress':json.dumps(progress,ensure_ascii=False),'full300_complete':False}
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.headers.get('Host') not in {f'127.0.0.1:{PORT}',f'localhost:{PORT}'}:self.send_error(403);return
  path=urlsplit(self.path).path
  try:
   if path=='/':data=HTML.encode();kind='text/html; charset=utf-8'
   elif path=='/status.json':data=json.dumps(snapshot(),ensure_ascii=False).encode();kind='application/json; charset=utf-8'
   else:self.send_error(404);return
  except (OSError,ValueError):self.send_error(503);return
  self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'");self.end_headers();self.wfile.write(data)
 def log_message(self,*args):pass
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
