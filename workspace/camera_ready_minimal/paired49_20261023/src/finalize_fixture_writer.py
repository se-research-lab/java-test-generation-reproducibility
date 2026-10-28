"""Back up before fixing the v2 fixture's summary destination; no Java rerun."""
import ast,difflib,shutil,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit
src=BASE/'src/fixture_maven_runtime_v2.py'
bak=BASE/'evo_patch/backup/fixture_maven_runtime_v2_before_report_guard.py'
assert not bak.exists();shutil.copy2(src,bak);assert audit.sha(src)==audit.sha(bak)
audit.log('PRE_EDIT_BACKUP',path=str(src.relative_to(BASE)),backup=str(bak.relative_to(BASE)),sha256=audit.sha(src),reason='Unique report filename and overwrite guard only')
old=src.read_text(encoding='utf-8')
needle="rp=stage/'reports/maven_fixture_result.json';rp.write_text("
assert old.count(needle)==1
new=old.replace(needle,"rp=stage/'reports/maven_fixture_v2_result.json';assert not rp.exists();rp.write_text(")
ast.parse(new);src.write_text(new,encoding='utf-8')
diff=BASE/'evo_patch/patches/003_fixture_summary_write_guard.diff'
assert not diff.exists()
diff.write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='v2_executed_source',tofile='v2_with_unique_summary_guard')),encoding='utf-8')
audit.log('FIXTURE_WRITER_GUARDED',path=str(src.relative_to(BASE)),before_sha256=audit.sha(bak),after_sha256=audit.sha(src),diff_sha256=audit.sha(diff),
    validation='Python AST parses; only derived report path and refusal-to-overwrite changed; no Java rerun needed',
    execution_provenance='The exact source used for attempt10 is preserved in the backup; the guarded version was not used to produce attempt10.')
print('Unique destination guard added; exact executed source preserved.')
