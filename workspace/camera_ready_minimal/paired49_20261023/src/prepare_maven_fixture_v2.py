"""Correct a fixture-only POM default; preserve the first failed integration attempt."""
import difflib,shutil,sys
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];sys.path.insert(0,str(BASE));import audit

source=BASE/'src/fixture_maven_runtime.py'
backup=BASE/'evo_patch/backup/fixture_maven_runtime_v1.py'
target=BASE/'src/fixture_maven_runtime_v2.py'
assert not backup.exists() and not target.exists()
shutil.copy2(source,backup);assert audit.sha(source)==audit.sha(backup)
audit.log('FIXTURE_DEFINITION_BACKUP',source=str(source.relative_to(BASE)),backup=str(backup.relative_to(BASE)),sha256=audit.sha(source))
old=source.read_text(encoding='utf-8')
assert old.count("('project.build.sourceEncoding','UTF-8'),('surefireArgLine','')")==1
assert old.count("'fixtures/maven_runtime_09'")==1
new=old.replace("('project.build.sourceEncoding','UTF-8'),('surefireArgLine','')","('project.build.sourceEncoding','UTF-8')").replace("'fixtures/maven_runtime_09'","'fixtures/maven_runtime_10'")
target.write_text(new,encoding='utf-8')
diff=BASE/'evo_patch/patches/002_fixture_only_empty_property.diff'
diff.write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='fixture_v1',tofile='fixture_v2')),encoding='utf-8')
audit.log('FIXTURE_DEFINITION_CORRECTION',new_file=str(target.relative_to(BASE)),sha256=audit.sha(target),diff_sha256=audit.sha(diff),
    reason='Fixture v1 introduced an empty surefireArgLine property absent from the inspected original POM builder; early interpolation removed the JaCoCo agent. Remove only this fixture-added default, leave shared code and all attempt09 outputs intact.',
    original_experiment_edits=0)
print(str(target))
