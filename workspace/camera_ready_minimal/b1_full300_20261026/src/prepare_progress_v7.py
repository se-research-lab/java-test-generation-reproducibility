"""Prepare the current human-readable handoff, retaining every prior draft."""
import sys
from maven_adapter_v1 import R,sha,dump
B=R.parent/'paired49_20261023';sys.path.insert(0,str(B));import audit
source=R/'src/record_progress_v6.py';target=R/'src/record_progress_v7.py'
text=source.read_text(encoding='utf-8').replace('v6','v7').replace('V6','V7')
text=text.replace('Gradle_recipe_v2','Gradle_recipe_v3').replace('gradle_native_recipe_v2/result.json','gradle_native_recipe_v3/result.json')
text=text.replace('Recipe Gradle v2 mới qua kiểm thuần Python:','Recipe Gradle v3 mới qua kiểm thuần Python:')
text=text.replace('Recipe Gradle v3 mới qua kiểm thuần Python: ràng buộc sandbox, giữ thứ tự classpath, cho hai lệnh đo dùng lại đúng sealed configuration.', 'Recipe Gradle v3 mới qua kiểm thuần Python: ràng buộc sandbox, giữ thứ tự classpath và legacy exact-focal target, kế thừa tài nguyên/process gate của task gốc, cho hai lệnh đo dùng lại đúng sealed configuration.')
text=text.replace('012 đã khởi động được EvoSuite và sinh native suite, nhưng measurement bị license-header check của dự án chặn. Kết quả strict0 được giữ; không sửa header của native test hoặc tự thêm skip-license.', '012 và023 đã khởi động được EvoSuite và sinh native suite, nhưng measurement bị license-header check của dự án chặn.016 timeout generation240s và được dừng theo owned process tree, không đổi timeout. Ba kết quả strict0 được giữ; không sửa header của native test hoặc tự thêm skip-license.')
text=text.replace('2. **P1 Gradle:** fixture', '2. **P1 Gradle:** audit lịch sử xác nhận10 GPT build thành công và10 PIT CSV;6 report có killing-test xác nhận owner,4 report zero có mutant nhưng chưa thể xác nhận owner chỉ bằng killing-test. CSV không cho biết engine version. Báo cáo tại `audit/gradle_g0_measurement_v1/REPORT.md`. Giữ đúng target FQCN của Gradle gốc, không tự thêm nested targets; đối chiếu miền mutant quan sát được độc lập với trạng thái killed trước quality claim. Tiếp tục fixture')
text=text.replace("R/'WINDOWS_CP_TRANSPORT_AMENDMENT_V3_DRAFT.md'","R/'WINDOWS_CP_TRANSPORT_AMENDMENT_V3.md',R/'audit/gradle_g0_measurement_v1/REPORT.md',R/'audit/gradle_g0_measurement_v1/result.json'")
text=text.replace('Gradle40 chưa được admit benchmark.\\n','Gradle40 chưa được admit benchmark; recipe mới nhất là gradle_native_recipe_v3.py, còn cần runtime fixture.\\n')
compile(text,str(target),'exec')
with target.open('x',encoding='utf-8') as f:f.write(text)
final='''# Maven v3 — classpath-file đã nghiệm thu và áp dụng

Bản này cập nhật draft trước admission. Bằng chứng chính: `admission_maven_v3.json`, `measurement_result_map_v3.json`, `validation/long_classpath_fixture_v1/validation_result.json` và ba folder `jobs/012_cpfile_v3`, `016_cpfile_v3`, `023_cpfile_v3`.

## Phạm vi được khóa

Chỉ khi Windows serialized command vượt32.767 UTF-16 units gồmNUL, bridge thay cặp `-projectCP <chuỗi>` bằng CLIproperty `-DCP_file_path=<file thuộc job>`. Chuỗi classpath, thứ tự và duplicates được giữ nguyên, hash và inverse-argv kiểm trước spawn. Tùy chọn sinh test, JDK, seed, search60s, timeout240s và conditional retry E49 giữ nguyên. Classpath được kiểm tools/dependency hashes trước transform.

Tính năng này có sẵn trong [Properties.java EvoSuite1.2.0](https://github.com/EvoSuite/evosuite/blob/v1.2.0/client/src/main/java/org/evosuite/Properties.java#L1336); cơ chế child JVM dùng classpath-file ở [TestGeneration.java](https://github.com/EvoSuite/evosuite/blob/v1.2.0/master/src/main/java/org/evosuite/executionmode/TestGeneration.java#L543). LocalJAR và runtime fixture đã đối chiếu. Fixture33.133→745units PASS, sinh1suite,6/6mutants killed và đủ JaCoCo/PIT/source/bytecode guard; đây là fixture tổng hợp, không phải dữ liệu300class.

## Quy tắc recovery và kết quả thực tế

012/016/023 ban đầu chưa spawn Java do WinError206. Quyết định dùng một kết quả theo policy mới bất kể score đã khóa trước generation thực của ba class; không chọn giá trị lớn nhất. Source, production bytecode và ordered CP được đối chiếu với lần chưa spawn, chỉ cho phép di chuyển đường dẫn repo sang sandbox riêng. Ba lần lỗi cũ, raw result và archive không bị thay.

- 012: sinh được native suite; measurement bị license-header plugin chặn; strict0.
- 016: generation hết240s; dừng đúng PID/start-time cùng descendants, không lỗi teardown; strict0.
- 023: sinh được native suite; measurement bị license-header plugin chặn; strict0.

Không thêm skip-license hoặc sửa native generated source. Không có GPT request/remeasurement mới. Repeated subset không được khởi động lại. Technical attempt và actual process start được đếm riêng, không được gọi là independent repeated-run evaluation.

## Bảo vệ dữ liệu và preview

49E1 cũ được tái sử dụng; profile/seed/input giữ khóa. Measurement map v3 kế thừa map v2 của003 và chỉ thêm recovery cho ba launch failure. Kết quả theo từng class và5RQ của GPT gốc không đổi. Chưa phân tích hoặc sửa paper từ một tập E1 chưa đủ300.

V3 còn sửa writer preview: snapshot chỉ chứa7trường public; temp/backup/hash độc quyền; retry sharing error trong giới hạn, lỗi I/O được audit riêng và không tự giết generation. Guard integrity vẫn dừng experiment. File.tmp lỗi v2 và log đã được backup, không xóa.

Đây là sửa transport/integration được quyết định sau khi thấy lỗi launch. Không mô tả như preregistration hoặc tác động chỉ của assertions. Mọi source cũ và raw evidence được giữ riêng; code thực nghiệm không được công khai.
'''
with (R/'WINDOWS_CP_TRANSPORT_AMENDMENT_V3.md').open('x',encoding='utf-8') as f:f.write(final)
audit.log('B1_HANDOFF_V7_PREPARED',source_sha256=sha(target),prior_source_sha256=sha(source),amendment_sha256=sha(R/'WINDOWS_CP_TRANSPORT_AMENDMENT_V3.md'));print('Prepared reporterV7 and final transport-method note; no experiment calls')
