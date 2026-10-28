"""Package private audit tables and a clean source-only Methods draft."""
import csv,json,sys,zipfile
from datetime import datetime,timezone
from pathlib import Path
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023'
sys.path.insert(0,str(B))
import audit
OUT=R/'policy_attempt_history_v2'
first=R/'manuscript_policy_audit_v1'
draft=R/'manuscript_policy_audit_v2'
assert not draft.exists()
draft.mkdir()
copied=[]
for p in first.rglob('*'):
    if not p.is_file() or p.suffix.lower() not in {'.tex','.bib','.cls','.bst'}:continue
    dest=draft/p.relative_to(first);dest.parent.mkdir(parents=True,exist_ok=True)
    with p.open('rb') as f,dest.open('xb') as t:t.write(f.read())
    assert sha(dest)==sha(p)
    copied.append({'source_path':str(p),'source_sha256':sha(p),'relative':dest.relative_to(draft).as_posix()})
method=draft/'sections/03_method.tex'
with (OUT/'03_method_before_language_cleanup.tex').open('xb') as f:f.write(method.read_bytes())
text=method.read_text(encoding='utf-8')
for old,new in [('fixed49 suites','fixed 49 suites'),('Surefire2.17','Surefire 2.17'),
                ('class003','class 003'),('reported300-class','reported 300-class'),
                ('its153 subjects','its 153 subjects'),("GPT's61/45/300","GPT's 61/45/300")]:text=text.replace(old,new)
text=text.replace('No per-class maximum is selected, but post-outcome policy adoption remains a validity limitation.',
                  'The recorded selection code uses explicit mappings rather than a maximum-score operator; post-outcome policy adoption remains a validity limitation.')
method.write_text(text,encoding='utf-8')
with (draft/'README_DRAFT.md').open('x',encoding='utf-8') as f:
    f.write('# Source-only Methods policy-disclosure draft\n\nCopied from manuscript_policy_audit_v1; wording/spacing cleaned in sections/03_method.tex only. The original private15-page release remains unchanged. This audit did not compile/render a PDF or verify15-page fit. Do not replace the submission PDF/ZIP with this source-only draft.\n\nEnvironment support is explicitly asymmetric, earlier amendments are post-hoc where applicable, and V6 uses a locked conditional policy rather than identical effective POMs. No new experiments/results, source-code publication, artifact URL, author metadata or AI-disclosure edits are introduced.\n')
dump(draft/'SOURCE_PROVENANCE.json',{'at_utc':datetime.now(timezone.utc).isoformat(),'files_copied':copied,
     'changed_file':'sections/03_method.tex','before_sha256':sha(OUT/'03_method_before_language_cleanup.tex'),
     'after_sha256':sha(method),'PDF_compiled':False,'page_limit_checked':False,'original_release_changed':False})
with (OUT/'READ_ME_FIRST.md').open('x',encoding='utf-8') as f:
    f.write('''# Bàn giao audit policy/attempts

Đọc [REPORT.md](REPORT.md) để thấy kết luận và ngoại lệ, [CLASS_HISTORY300.md](CLASS_HISTORY300.md) để xem từng class. CSV đầy đủ gồm `class_policy_history300.csv`, `generation_measurement_diagnostic_attempts.csv`, `command_history_all.csv`, `dependency_selector_changes.csv`, `policy_timeline.csv`.

**V6:**165 actual searches/153class,12 technical retries;266 selected native source files khớp generation-attempt archive; tối đa1 measurement/class. Profile/seed/budget và conditional rule được khóa trước V6. **Toàn E1 không bất biến từ đầu:** có post-failure remeasurement, dependency/selector amendments và003 override sau khi biết outcome. Xem đúng timing/selection role, không gọi mọi lần là predeclared retry.

**Methods source mới nhất:** `../manuscript_policy_audit_v2/sections/03_method.tex`. V1 được giữ như bản draft đầu. V2 chỉ làm rõ/cải thiện câu chữ và giữ disclosure đối xứng/asymmetry đúng bằng chứng. Chưa compile/render PDF hoặc kiểm15 trang; không thay source/PDF/ZIP release cũ. Bảng hỗ trợ môi trường mở rộng ở `METHODS_ENVIRONMENT_ASYMMETRY.md`; đường dẫn v1 trong ghi chép lịch sử được giữ để audit.

`../EXPERIMENT_CONFIGURATION_FREEZE_20261026.json` ghi yêu cầu hiện tại: không mở thêm sửa test/dependency/selector hoặc corpus execution để đạt build; tiếp tục offline audit/biên tập. Khóa mới không hồi tố các amendment cũ. Không đổi score/maps, không remeasure GPT.

ZIP audit đi kèm là tài liệu riêng tư để review, **không phải gói camera-ready cuối hoặc public experiment-code release**. Không có Java focal source, API keys hoặc file settings credentials trong ZIP; argv/path/hash được giữ vì cần provenance. Historical G0/E0 referenced as archived observations; this is not a claimed reconstruction of all attempts of every abandoned draft.
''')
# Recheck the sealed first package as historical, then include additions in a
# new manifest. The old manifest/source packages remain byte-preserved.
old_manifest=load_manifest= json.loads((OUT/'PACKAGE_MANIFEST.json').read_text(encoding='utf-8'))
for row in old_manifest['files']:assert sha(R.parents[1]/row['path'])==row['sha256']
all_files=[p for p in OUT.iterdir() if p.is_file()]+[p for p in draft.rglob('*') if p.is_file()]+[R/'EXPERIMENT_CONFIGURATION_FREEZE_20261026.json']
manifest=OUT/'DELIVERY_MANIFEST.json'
dump(manifest,{'recorded_utc':datetime.now(timezone.utc).isoformat(),
              'files':[{'workspace_relative':p.relative_to(R.parents[1]).as_posix(),'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(set(all_files))]})
all_files.append(manifest)
archive=R/'policy_history_private_audit_v1.zip'
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    for p in sorted(set(all_files)):
        if p.is_relative_to(OUT):name='policy_history/'+p.relative_to(OUT).as_posix()
        elif p.is_relative_to(draft):name='manuscript_source_draft/'+p.relative_to(draft).as_posix()
        else:name=p.name
        z.write(p,name)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    for p in sorted(set(all_files)):
        name='policy_history/'+p.relative_to(OUT).as_posix() if p.is_relative_to(OUT) else ('manuscript_source_draft/'+p.relative_to(draft).as_posix() if p.is_relative_to(draft) else p.name)
        assert __import__('hashlib').sha256(z.read(name)).hexdigest()==sha(p)
dump(R/'policy_history_private_audit_v1_zip_receipt.json',{'zip_path':str(archive),'zip_sha256':sha(archive),
     'bytes':archive.stat().st_size,'files':len(set(all_files)),'all_entries_byte_verified':True,
     'submission_release':False,'public_code_release':False,'new_experiment_calls':0})
audit.log('B1_POLICY_HISTORY_PRIVATE_DELIVERY_PACKAGED',zip_sha256=sha(archive),
          delivery_manifest_sha256=sha(manifest),Methods_v2_sha256=sha(method),
          original_release_changed=False,new_experiment_calls=0,GPT_API_calls=0)
print(json.dumps({'archive':str(archive),'zip_sha256':sha(archive),'files':len(set(all_files)),
                  'Methods_latest':str(method),'PDF_compiled':False,'original_release_changed':False,'new_experiment_calls':0},indent=2))
