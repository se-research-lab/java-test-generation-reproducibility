"""Prepare a fresh observation; prior reports/source remain unchanged."""
import ast,sys
from maven_adapter_v1 import R,sha
B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit
source=R/'src/assess_runtime_stability_v1.py'
target=R/'src/assess_runtime_stability_v2.py'
text=source.read_text(encoding='utf-8').replace('runtime_stability_v1','runtime_stability_v2')
text=text.replace('from checkpoint_archive_guard_v2 import verify','from checkpoint_archive_guard_v2 import verify\nfrom run_maven_b1_v2 import guards')
text=text.replace("first=snapshot(identity)","guards(load(R/'admission_maven_v6.json'))\nfirst=snapshot(identity)")
key="dump(OUT/'sample2.json',second)"
extra='''
prior_processes={(p['pid'],p['create_time']):p for p in first['owned_process_tree']}
java_deltas=[]
for child in second['owned_process_tree']:
    previous=prior_processes.get((child['pid'],child['create_time']))
    if previous and child['name'].lower() in {'java.exe','javaw.exe'}:
        java_deltas.append({'pid':child['pid'],'CPU_seconds_in_window':child['CPU_seconds']-previous['CPU_seconds'],
                            'RSS_change_bytes':child['RSS_bytes']-previous['RSS_bytes']})
'''
assert text.count(key)==1
text=text.replace(key,key+extra)
text=text.replace("'owner_identity':identity,'samples_seconds_apart':elapsed", "'owner_identity':identity,'samples_seconds_apart':elapsed,'Java_same_identity_deltas':java_deltas")
text=text.replace('12 class chưa chấm và40 Gradle chưa admit',"{second['runtime_status']['maven_deferred_unscored']} class chưa chấm và40 Gradle chưa admit")
text=text.replace('B1_RUNTIME_STABILITY_OBSERVED_READONLY','B1_RUNTIME_STABILITY_V2_OBSERVED_READONLY')
text=text.replace('RAM host còn',"Java cùng PID/create-time có mức tăng CPU: `{java_deltas}`. Không suy memory leak từ RSS của một khoảng ngắn.\n\nRAM host còn")
ast.parse(text)
with target.open('x',encoding='utf-8') as f:
    f.write(text)
audit.log('B1_RUNTIME_STABILITY_V2_PREPARED',prior_source_sha256=sha(source),source_sha256=sha(target),
          experiment_changes=0,reason='New resource/capacity observation; keep old insufficient-disk report as historical evidence')
print('Prepared diagnostic v2; original observations unchanged; no experiment/process changes')
