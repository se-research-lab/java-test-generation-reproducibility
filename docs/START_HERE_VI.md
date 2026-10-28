# Bắt đầu sử dụng folder source

Folder này được tạo riêng để bạn tự quản lý và push dần lên GitHub. Source được copy nguyên bản từ workspace, kèm cấu hình, policy và các bảng kết quả nhỏ đã có. Không tải thư viện, không chạy GPT/EvoSuite/Maven/Gradle và không sửa source thí nghiệm gốc.

## Đọc và kiểm tra

1. Mở README ở root và `SOURCE_LAYOUT.md` để phân biệt G0/E0, E49, E1 full-cohort và completion30.
2. Chạy `python tools/verify_bundle.py` từ root. Lệnh này chỉ kiểm hash, dùng Python standard library.
3. Xem `manifests/PYTHON_SOURCE_INDEX.csv`: toàn bộ file Python, mô tả, main guard và các tên CLI đọc tĩnh từ source. Không tự chạy mọi file có main guard; một số là admission, batch, repair hoặc script soạn hồ sơ lịch sử.
4. Đọc `RUN_GUIDE.md` để chọn đúng entry point, input, output và điều kiện môi trường.

## Tìm code chính

- GPT/E0 lịch sử: `workspace/scripts_v2/rbl4_v2_runner.py` và `workspace/scripts_v2/AgoneTest/`.
- E1 fixed49: `workspace/camera_ready_minimal/paired49_20261023/src/`; các hàm AgoneTest sửa riêng ở `evo_patch/working/AgoneTest/`.
- E1 Maven/Gradle và completion: `workspace/camera_ready_minimal/b1_full300_20261026/src/`.
- Ba adapter bắt buộc: `workspace/camera_ready_minimal/b1_full300_20261026/adapters/`.
- Kết quả300 đã chốt: `workspace/camera_ready_minimal/b1_full300_20261026/completion_amendment_v1/final300_offline_v1/`.

## Các file vẫn lấy từ workspace đang có

JDK/Maven/Gradle, JAR EvoSuite/runtime/TestSmellDetector, compiledrepos, caches và sqlite snapshots không copy vào source bundle. Chúng vẫn ở vị trí local cũ, không cần tải lại trong công việc này. Generated tests/raw PIT/JaCoCo/XML/logs vẫn ở `jobs/` và các workspace lịch sử. Các đường dẫn/hashes của chúng được lưu trong metadata. Thiếu các asset đó trên máy khác không có nghĩa class thất bại; đó là thiếu điều kiện tái chạy.

## Lưu ý về phiên bản

Có nhiều V1–V6 và amendment vì đây là lịch sử thật. Không đổi tên/gộp chúng thành một runner mới rồi coi toàn bộ kết quả được tạo bằng cùng cấu hình. Class3 có đo chẩn đoán sau lỗi; giữ initial result và sensitivity. Repeated subset chưa hoàn chỉnh, source liên quan được lưu để đầy đủ code nhưng không thuộc các kết quả paper.

Không có lệnh cài thư viện trong hướng dẫn. `DEPENDENCIES_AND_LOCAL_ASSETS.md` chỉ chỉ ra requirements đã tồn tại và runtime lịch sử. `PUSH_TO_GITHUB.md` hướng dẫn push bằng tay; folder chưa được `git init`, tạo remote hoặc upload.

Bốn file nháp/backup có lỗi cú pháp được giữ nguyên và liệt kê ở [ARCHIVED_CODE_NOTES.md](ARCHIVED_CODE_NOTES.md). Đây không phải các entry point chính được hướng dẫn chạy.
