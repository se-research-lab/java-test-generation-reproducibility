"""HTTP-only QA for a read-only loopback preview; no experiment endpoint."""
import json, sys, urllib.request, urllib.error
from maven_adapter_v1 import R, sha, dump
B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit

checks=[]
status=None
for route,expected in [('/',200),('/status.json',200),('/manifest.json',200),('/src/',404),('/jobs/066/result.json',404),('/audit/',404)]:
    try:
        with urllib.request.urlopen('http://127.0.0.1:8766'+route,timeout=5) as response:
            code=response.status
            content=response.read()
    except urllib.error.HTTPError as ex:
        code=ex.code
        content=ex.read()
    assert code==expected
    checks.append({'route':route,'status':code})
    if route=='/status.json':
        status=json.loads(content)
        assert status['runner_liveness']=='NO_V5_OWNER_RECORD'
        assert status['running']==0 and status['benchmark_admitted'] is False
        assert status['live_process_check_at_utc'].endswith('+00:00')
    if route=='/manifest.json':
        rows=json.loads(content)
        assert len(rows)==300 and all(set(r)=={'sample_index_1based','class_key','repo_id','focal_class','build_tool','seed','status'} for r in rows)
for label,request,expected in [
    ('POST disabled',urllib.request.Request('http://127.0.0.1:8766/',data=b'',method='POST'),501),
    ('foreign Host denied',urllib.request.Request('http://127.0.0.1:8766/',headers={'Host':'untrusted.invalid'}),403)]:
    try:
        with urllib.request.urlopen(request,timeout=5) as response:
            code=response.status
    except urllib.error.HTTPError as ex:
        code=ex.code
    assert code==expected
    checks.append({'check':label,'status':code})
dump(R/'validation/monitor_v3_http_v1/result.json',{'status':'PASS_HTTP_AND_LIVENESS_OVERLAY_ONLY',
     'checks':checks,'status_observed':status,'manifest_rows':300,'public_manifest_fields':7,
     'new_experiments':0,'GPT_API_calls':0,'render_QA_performed':False,
     'server_sha256':sha(R/'monitor/serve_v3.py'),'health_helper_sha256':sha(R/'src/preview_runner_health_v1.py')})
audit.log('B1_MONITOR_V3_HTTP_VALIDATED_NO_EXPERIMENT_ENDPOINT',checks=len(checks),
          server_sha256=sha(R/'monitor/serve_v3.py'),render_QA_performed=False,new_experiments=0)
print('PASS:8 HTTP checks;300 rows/7 fields; PID-aware overlay; source/audit404, POST501, foreignHost403; no browser render QA')
