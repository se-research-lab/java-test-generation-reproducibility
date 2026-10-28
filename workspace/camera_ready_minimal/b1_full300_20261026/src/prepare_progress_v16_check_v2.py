"""Keep failed diagnostic source/log; correct only psutil Windows path type."""
import ast,sys
from maven_adapter_v1 import R,sha
B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit
source=R/'src/record_progress_v16_check_v1.py'
target=R/'src/record_progress_v16_check_v2.py'
text=source.read_text(encoding='utf-8')
assert text.count('psutil.disk_usage(R).free')==1
text=text.replace('psutil.disk_usage(R).free','psutil.disk_usage(str(R)).free')
ast.parse(text)
with target.open('x',encoding='utf-8') as f:f.write(text)
audit.log('B1_V16_DIAGNOSTIC_WINDOWS_PATH_CORRECTED',source_sha256=sha(target),prior_failed_source_sha256=sha(source),
          correction='psutil Windows requires string path; prior diagnostic stopped before sampling/output; no experiment/config changes',
          experiment_changes=0,new_experiment_calls=0)
print('Diagnostic v2 prepared; failedv1 preserved; no runner/configuration edit')
