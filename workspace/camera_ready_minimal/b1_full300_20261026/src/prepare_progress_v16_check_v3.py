"""Keep diagnosticv1/v2; prevent counting frozen-POM deferrals as unattempted."""
import ast,sys
from maven_adapter_v1 import R,sha
B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit
source=R/'src/record_progress_v16_check_v2.py'
target=R/'src/record_progress_v16_check_v3.py'
text=source.read_text(encoding='utf-8')
old="    elif not base.exists():not_created.append(i)"
new="""    elif (R/'runtime/non_junit4_deferrals_v1'/f'{i:03d}.json').exists() or (R/'runtime/pom_input_deferrals_v1'/f'{i:03d}.json').exists():
        pass  # Reviewed unscored class, including a future POM with no job folder.
    elif not base.exists():not_created.append(i)"""
assert text.count(old)==1
text=text.replace(old,new)
ast.parse(text)
with target.open('x',encoding='utf-8') as f:f.write(text)
audit.log('B1_V16_DIAGNOSTIC_DOUBLE_COUNT_CORRECTED',prior_failed_source_sha256=sha(source),source_sha256=sha(target),
          correction='Exclude reviewed unscored fixed-input class from no-job-folder count; retain fixed300; no experiment or score edits',
          experiment_changes=0,new_experiment_calls=0)
print('Diagnostic v3 prepared; old failed checks preserved; count-only correction')
