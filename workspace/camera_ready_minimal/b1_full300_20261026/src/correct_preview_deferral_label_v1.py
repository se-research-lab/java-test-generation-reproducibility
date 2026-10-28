"""Display-only correction; never changes the runner, raw status or results."""
import sys,urllib.request
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit
page=R/'monitor/dist_v2/index.html'
backup=R/'backups/monitor_index_before_dynamic_deferral_label_v1.html'
assert not backup.exists(),'Keep prior preview backup'
text=page.read_text(encoding='utf-8')
old="li.textContent=b;$('blockers').append(li)"
new="li.textContent=/^\\d+ class đầu vào\\/provider chưa chấm;/.test(b)&&Number.isInteger(s.maven_deferred_unscored)?b.replace(/^\\d+/,String(s.maven_deferred_unscored)):b;$('blockers').append(li)"
assert text.count(old)==1
with backup.open('xb') as f:
    f.write(page.read_bytes())
prior=sha(page)
page.write_text(text.replace(old,new),encoding='utf-8')
with urllib.request.urlopen('http://127.0.0.1:8766/',timeout=5) as response:
    served=response.read().decode('utf-8')
assert new in served and old not in served
dump(R/'audit/preview_deferral_label_v1.json',{'scope':'one display label takes the actual integer from status instead of stale literal12',
     'backup_path':backup.relative_to(R).as_posix(),'backup_sha256':sha(backup),'before_sha256':prior,
     'after_sha256':sha(page),'served_new_page_HTTP':True,'browser_render_checked':False,
     'experiment_source_changed':False,'raw_status_changed':False,'metric_or_denominator_changed':False,
     'new_experiment_calls':0})
audit.log('B1_PREVIEW_DYNAMIC_DEFERRAL_LABEL_ONLY',before_sha256=prior,after_sha256=sha(page),
          backup_sha256=sha(backup),experiment_changes=0,raw_status_changes=0)
print('Preview label corrected with backup; reads actual deferred count; no experiment/raw-status edit or restart')
