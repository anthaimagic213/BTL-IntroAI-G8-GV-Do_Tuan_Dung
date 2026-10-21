# Kết quả kiểm thử

## Cập nhật sau refactor module — 17/10/2026

**Các kết quả 48 test và browser smoke bên dưới thuộc bản trước refactor, không phải bằng chứng bản module đã đạt toàn bộ.**

- Log lần chạy full suite trước tại `D:\Sudoku_Project_IntroAI\.pytest-refactor.log`:
  **158 passed, 4 failed, 1 warning**. Bốn ca `test_sample_solution_and_history[config0..3]`
  nhận `limit_reached` thay vì `success`: inference `none`, MRV tắt,
  kết hợp hai lựa chọn LCV và hai chiến lược quay lui.
- Lần cập nhật tài liệu này chạy lại nhóm backend/API dưới đây:
  **58 passed, 104 deselected, 1 warning** (1,95 giây trên môi trường hiện tại).
- Nhóm này kiểm tra contract hai endpoint trên 24 cấu hình DFS và Local Search,
  MRV/LCV, lan truyền AC-3, FC phát hiện miền rỗng, rollback nhánh MAC,
  Local Search và kết thúc có kiểm soát khi hết ngân sách.
- Không chạy lại toàn suite trong lần sửa docs; không sửa solver/test để che kết quả thất bại.
- Warning hiện tại là deprecation giữa Starlette TestClient và httpx, không phải test thất bại.
- Script browser smoke còn dùng dropdown/trường metrics/endpoint theo bản cũ;
  chưa dùng nó để xác nhận UI module mới. Hướng dẫn browser bên dưới mang tính lịch sử.

Lệnh nhóm test đã chạy (PowerShell):

```powershell
cd D:\Sudoku_Project_IntroAI
& D:\Sudoku_Project_IntroAI\.venv\Scripts\python.exe -m pytest -q D:\Sudoku_Project_IntroAI\tests\test_solver.py -k 'api_contract or mrv_and_lcv or ac3_propagates or fc_detects or mac_restores or min_conflicts or resource_limits'
```

Xem giải thích backend hiện tại tại `D:\Sudoku_Project_IntroAI\docs\BACKEND.md`.

---

## Kết quả lịch sử trước refactor module

## Môi trường kiểm chứng
- Windows, Python 3.12; Node 24.14.1.
- FastAPI 0.120.4, Pydantic 2.12.3, Uvicorn 0.38.0, httpx 0.28.1, pytest 8.4.2.
- Playwright 1.64.0 chạy Chrome headless có sẵn trên máy.
- Playwright chỉ là công cụ kiểm thử tùy chọn, không phải dependency chạy ứng dụng.

## Backend / API: 48 test đạt
Lệnh: `python -m pytest -q` từ thư mục dự án.

Đã kiểm tra:
- Năm thuật toán tìm kiếm hệ thống giải đúng đề mẫu, kiểm tra riêng hàng/cột/khối.
- Cả sáu thuật toán xử lý bảng đã giải.
- Mọi snapshot giữ nguyên đề, input gốc không bị sửa, snapshot deepcopy độc lập.
- Naive không PRUNE; FC/MRV/LCV/MAC có PRUNE.
- Counters khớp history và metrics cuối.
- Đề không trùng số trực tiếp nhưng vô nghiệm được báo đúng bởi năm thuật toán DFS.
- Phục hồi domains sau thất bại FC/MRV/LCV và nhánh MAC thất bại.
- MRV/LCV chọn đúng trên miền thiết kế riêng; AC-3 lan truyền singleton qua nhiều cung.
- FC phát hiện domain rỗng ngay.
- Min-Conflicts giữ bảng đầy, không sửa đề, không phát sinh PRUNE/BACKTRACK, giải được ca một ô trống.
- Min-Conflicts hết ngân sách là not_found; restart sau plateau không reset ngân sách toàn cục.
- Giới hạn thời gian/history trả limit_reached và có FAIL cuối.
- API đúng schema; từ chối kích thước sai, bool, chuỗi, số thực, số ngoài miền, đề trùng và ID lạ.
- Frontend assets và Swagger được phục vụ đúng.

**Không suy rộng:** test một ô trống không có nghĩa Min-Conflicts luôn giải được đề mẫu hay mọi đề.
Không có yêu cầu bảo đảm local search thành công; cần trình bày giới hạn này khi bảo vệ.

## Replay unit tests: 4 test đạt
Lệnh: `node --test D:\Sudoku_Project_IntroAI\tests\replay.test.mjs`.

- Thứ tự bước và callback kết thúc đúng một lần.
- Pause hủy timer; resume không mất/nhân đôi bước.
- Đổi tốc độ tác động lần lập lịch kế tiếp.
- Load/stop loại timer và history cũ.
- `node --check` đạt cho app.js và replay.js.

## Trình duyệt thật / HTTP server thật: đạt
Lệnh tùy chọn:
```powershell
cd D:\Sudoku_Project_IntroAI
python -m pip install -r requirements-browser.txt
# Chỉ cần nếu không có Chrome/Edge tại đường dẫn thông thường:
python -m playwright install chromium
python tests/browser_smoke.py
```

Script tự khởi động Uvicorn ở cổng tạm, mở Chrome headless và đóng server khi xong.
Kiểm tra 81 input, lọc chữ, border 1px/3px, cảnh báo local search, API thật và replay,
readonly lúc giải, pause/resume, board cuối bằng snapshot backend, metrics assignments,
log tự cuộn, giải lại bằng input gốc, clear lúc replay, lỗi HTTP 422 và không có JS page error.
Kiểm tra không tràn ngang ở viewport 1440, 900, 390px.
Ảnh chụp đã tạo và đọc lại: `docs/screenshots/desktop.png`, `docs/screenshots/mobile.png`.

### Các lỗi bắt được trong quá trình kiểm chứng
1. Test số dòng restart kỳ vọng sai 505: sửa phép cộng thành 501 + 2 + 1 = 504.
2. Timer giả không phát hiện `Illegal invocation` khi gọi browser setTimeout qua thuộc tính engine:
   sửa bằng wrapper gọi `globalThis.setTimeout` và `globalThis.clearTimeout`.
3. Auto-scroll lệch dòng cuối khi status đổi chiều cao layout: bổ sung cuộn lại trong requestAnimationFrame.

## Phạm vi chưa kiểm chứng
- Chưa kiểm thử Safari/Firefox hoặc thiết bị di động vật lý (đã kiểm viewport bằng Chrome headless).
- Chưa load-test nhiều người dùng đồng thời, chưa đánh giá hiệu năng production.
- Không đo thời gian làm chuẩn so sánh thuật toán: hardware và chi phí ghi history ảnh hưởng kết quả.
- Không xác minh tính duy nhất của đề hoặc hỗ trợ Sudoku 16×16.