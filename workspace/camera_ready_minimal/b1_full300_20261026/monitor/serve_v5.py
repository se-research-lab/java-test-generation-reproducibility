"""Read-only loopback monitor: never starts experiments; no workspace file server."""
import json,sys
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlsplit
from datetime import datetime,timezone
R=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(R/'src'))
from preview_runner_health_v3 import view_status
PORT=8766
PUBLIC_FIELDS=('sample_index_1based','class_key','repo_id','focal_class','build_tool','seed','status')
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  if self.headers.get('Host') not in {f'127.0.0.1:{PORT}',f'localhost:{PORT}'}:
   self.send_error(403);return
  path=urlsplit(self.path).path
  try:
   if path=='/':content=(R/'monitor/dist_v2/index.html').read_bytes();kind='text/html; charset=utf-8'
   elif path=='/status.json':content=json.dumps(view_status(json.loads((R/'status.json').read_text(encoding='utf-8'))),ensure_ascii=False).encode('utf-8');kind='application/json; charset=utf-8'
   elif path=='/manifest.json':
    manifest=R/'runtime/manifest_live300.json'
    rows=json.loads((manifest if manifest.exists() else R/'manifest300.json').read_text(encoding='utf-8'))
    content=json.dumps([{k:r[k] for k in PUBLIC_FIELDS} for r in rows],ensure_ascii=False).encode('utf-8');kind='application/json; charset=utf-8'
   else:self.send_error(404);return
  except (OSError,ValueError):self.send_error(503,'Snapshot unavailable');return
  self.send_response(200);self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(content)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'");self.end_headers();self.wfile.write(content)
 def log_message(self,fmt,*args):
  sys.stdout.write(datetime.now(timezone.utc).isoformat()+' '+fmt%args+'\n');sys.stdout.flush()
if __name__=='__main__':
 server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
 print(f'Local: http://127.0.0.1:{PORT}',flush=True)
 try:server.serve_forever()
 except KeyboardInterrupt:pass
 finally:server.server_close()
