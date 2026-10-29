# Hướng dẫn sử dụng source và dữ liệu

Repo công khai: https://github.com/se-research-lab/java-test-generation-reproducibility

Snapshot source/data được paper dẫn là `86799597262e21749ef92fd0253c08a24619978d`. Các bản cập nhật README và manuscript trong checkout này được chuẩn bị để tác giả tự push. Không có commit, push, tải thư viện hoặc chạy thực nghiệm trong lần cập nhật tài liệu.

## Đọc theo thứ tự

1. [ARTIFACT_INDEX.md](ARTIFACT_INDEX.md) nối mô tả và bảng trong paper với đường dẫn file.
2. `data/dataset_result/README.md` mô tả final300, backup60, source frozen và baseline-build evidence. `data/compiledrepos/` đã có 30 snapshot repo; không cần copy lại.
3. `paper/camera_ready/` chứa PDF và LaTeX mới, cùng hướng dẫn build manuscript. Title giữ nguyên. Table 5 sửa G0 valid PIT reports thành 49/49.
4. `RESULTS_AND_POLICIES.md` phân biệt observed PIT, policy zero, unresolved, process gate và native test.
5. `RUN_GUIDE.md` ghi entry points lịch sử và điều kiện môi trường. Không tự chạy mọi file có main guard.

## Kiểm hash trước khi push

Từ root, chạy `python tools/verify_bundle.py`. Đây là kiểm file theo manifest; không build Java, không gọi API và không tái sinh test. COPY_MAP/PYTHON_SOURCE_INDEX là provenance của workspace bundle gốc, không phải khẳng định mọi file Python mới trong Data V3 đều thuộc index cũ.

## Phạm vi công bố

Có source G0/E0/E49/E1, primary result tables, Data V3 manifests/source/readiness logs và manuscript. Chưa có toàn bộ raw generated suites/PIT/JaCoCo/XML/logs, upstream CLASSES2TEST dump, caches và local inputs. Code/evidence của các phân tích bổ sung sau review ngày 29/10 giữ ở local, không được thêm vào repo. Các bảng audit/history cũ đã public được giữ nguyên.

E1 vẫn 221 observed scores + 58 policy zeros + 21 unknown; không gọi E1-full300 hoàn chỉnh. G0 không được hỗ trợ môi trường giống E1. RQ4 giới hạn theo cấu hình/pipeline; RQ5 củng cố ưu thế recorded process gate có điều kiện. Các giới hạn repeated runs, margin và equalized budgets vẫn còn.

Theo [PUSH_TO_GITHUB.md](PUSH_TO_GITHUB.md), tác giả chỉ stage các đường dẫn đã duyệt; không copy gói github_additions cũ hoặc toàn bộ folder thí nghiệm vào repo. Tác giả tự commit/push.
