"""Qualify immutable legacy cache artifact reads, without shared cache writes.

Gradle2.13 serializes cached artifact absolute paths. Private copied metadata
therefore returns original artifact paths. Permit only the exact pre-hashed
artifact files which have verified byte-identical private copies. All mutable
cache state remains in the private -g home. Source cache is verified in full
before/after, and artifacts are pinned before every process. No dependency or
test changes; no benchmark admission here.
"""
import ast,difflib,sys
from datetime import datetime,timezone
from maven_adapter_v1 import R,sha,dump
from projection_io_v1 import publish_json
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
old=R/'src/run_gradle_native_fixture_v4.py';new=R/'src/run_gradle_native_fixture_v5.py'
text=old.read_text(encoding='utf-8')
needle="for r in immutable:pins[str((PRIVATE_HOME/r['relative']).resolve())]=r['sha256']"
replacement=needle+"\n for r in immutable:\n  if r['relative'].startswith('caches/modules-2/files-2.1/'):\n   pins[str((original_cache/r['relative']).resolve())]=r['sha256']"
assert text.count(needle)==1;text=text.replace(needle,replacement)
needle="artifacts={str((PRIVATE_HOME/r['relative']).resolve()):r['sha256'] for r in immutable}"
replacement=needle+"\n  artifacts.update({str((original_cache/r['relative']).resolve()):r['sha256'] for r in immutable if r['relative'].startswith('caches/modules-2/files-2.1/')})"
assert text.count(needle)==1;text=text.replace(needle,replacement)
text=text.replace('gradle_native_runtime_fixture_v4','gradle_native_runtime_fixture_v5')
text=text.replace("'original_source_cache_bytes_unchanged':True,","'original_source_cache_bytes_unchanged':True,'legacy_absolute_artifact_paths':True,'cache_write_home':'private -g only; source artifacts immutable pinned reads',")
ast.parse(text)
with new.open('x',encoding='utf-8') as f:f.write(text)
out=R/'audit/gradle_fixture_legacy_cache_paths_v5';out.mkdir(exist_ok=False)
diff=out/'fixture.diff';diff.write_text(''.join(difflib.unified_diff(old.read_text(encoding='utf-8').splitlines(True),text.splitlines(True),fromfile=old.name,tofile=new.name)),encoding='utf-8')
primary=R/'cache_preparation_gradle_v1/gradle_user_home/wrapper/dists/gradle-2.13-all/1b9wlm73elu4cqnbc0rk7r7qn/gradle-2.13/src/dependency-management/org/gradle/internal/resource/cached/ivy/ArtifactAtRepositoryCachedArtifactIndex.java'
code=primary.read_text(encoding='utf-8');assert 'encoder.writeString(value.getCachedFile().getPath())' in code and 'new File(decoder.readString())' in code
dump(out/'preparation.json',{'scope':'synthetic fixture guard qualification only; no corpus admission','old_runner_sha256':sha(old),'new_runner_sha256':sha(new),'unchanged_recipe_sha256':sha(R/'src/gradle_native_recipe_v6.py'),'diff_sha256':sha(diff),'exact_legacy_primary_source':str(primary),'primary_source_sha256':sha(primary),'reason':'Private metadata copied from old Gradle retains absolute source artifact paths. Accept only pre-hashed files-2.1 artifacts with byte-identical verified private copies; pin both before every command.','mutable_cache_home':'private -g / GRADLE_USER_HOME only','source_cache_verification':'all original copied source cache files verified before and after each fixture','changes_to_dependency_versions_selectors_test_sources_generation_flags':0,'no_read_of_credentials_or_user_configuration':True,'benchmark_admitted':False,'new_EvoSuite_calls':0,'GPT_API_calls':0})
audit.log('B1_GRADLE_LEGACY_CACHE_PATHS_FIXTURE_V5_PREPARED',runner_sha256=sha(new),recipe_sha256=sha(R/'src/gradle_native_recipe_v6.py'),corpus_admitted=False,immutable_source_artifact_reads=True,original_cache_writes_authorized=False)
status=__import__('json').loads((R/'status.json').read_text(encoding='utf-8'))
status.update(phase='GRADLE_NATIVE_ADAPTER_QUALIFICATION',updated_utc=datetime.now(timezone.utc).isoformat(),running=0,active_sample_index=None,benchmark_admitted=False)
status['blockers']=['Đang kiểm adapter trên fixture tổng hợp, chưa khởi chạy Gradle40','20 Maven giữ nguyên deferred/unscored; không sửa POM/JUnit sau kết quả','Cache ghi riêng; Gradle cũ có đường dẫn artifact tuyệt đối, chỉ chấp nhận file đã pin hash và kiểm trước/sau','GPT và dữ liệu paper giữ nguyên']
receipt=publish_json(R/'status.json',status,label='gradle_qualification_v5');dump(out/'projection_receipt.json',receipt)
print('PASS: legacy artifact immutable-read guard prepared; native/configuration unchanged, no corpus executed')
