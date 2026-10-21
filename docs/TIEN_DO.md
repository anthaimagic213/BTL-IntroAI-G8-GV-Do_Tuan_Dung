# Nhật ký triển khai

## Cập nhật tài liệu backend sau refactor module — 17/10/2026

- Tài liệu hiện hành: `D:\Sudoku_Project_IntroAI\docs\BACKEND.md`.
- Contract hiện tại dùng `base_algorithm`, `inference`, `use_mrv`, `use_lcv`,
  `backtrack_strategy`; response dùng `config_summary` và metrics `total_*`.
- Một bộ khung DFS `backtrack()` dùng chung; CBJ có logic tập nguyên nhân;
  Local Search tách riêng; đo thời gian và peak cấp phát Python bằng tracemalloc.
- Đính chính kết quả: log full suite sau refactor ghi 158 đạt/4 thất bại do các ca
  đề mẫu không inference, không MRV trả `limit_reached` thay vì `success`.
- Lần sửa docs chạy nhóm backend/API chọn lọc: 58 đạt, 104 không chọn, 1 warning.
  Không thay đổi code xử lý. Nội dung phase bên dưới là lịch sử trước refactor.

## Khảo sát và đối chiếu bài giảng
- Dự án ban đầu chỉ có `L6_Thoa_man_rang_buoc.pdf` (43 trang).
- Đã dùng pypdf trích xuất phần chữ vào `lecture_extracted.txt` và đọc nội dung.
- Trang 3–7: biến, miền, ràng buộc và đồ thị CSP; 15–17: DFS/quay lui.
- Trang 26–28: MRV, Degree phá hòa, LCV; trang 29: Forward Checking.
- Trang 34–39: lan truyền, phù hợp cạnh, AC-3; 40–41: tìm kiếm cục bộ.
- Các slide hình ảnh (đặc biệt mã giả trang 17, 39) không có đầy đủ nội dung trong bản trích xuất chữ. Không tuyên bố đã đọc được chi tiết hình.

## Quyết định thiết kế
- FastAPI phục vụ API và frontend thuần, không có thuật toán giải phía trình duyệt.
- Chỉ hỗ trợ 9×9, khối 3×3; số 0 biểu thị ô trống.
- Contract lấy mục 5 làm chuẩn: `execution_time_ms`, `algorithm_used`.
- Bổ sung metrics từng bước; thời gian là thời gian backend tích lũy có tính cả ghi snapshot, không phải thời gian animation.
- Phân biệt `unsolvable` (DFS duyệt hết), `not_found` (local search hết ngân sách), `limit_reached` (giới hạn tài nguyên).
- Snapshot đầy đủ tốn bộ nhớ: giới hạn mặc định 30.000 sự kiện và 15 giây tính toán; luôn có bước kết thúc riêng.
- Min-Conflicts restart sau 500 bước không cải thiện, nhưng không reset ngân sách tổng 10.000 bước.

## Phase 1
- Đã tạo schemas Pydantic với số nguyên nghiêm ngặt 0–9, ma trận đúng 9×9 và enum action.
- Môi trường có sẵn FastAPI, Uvicorn, pytest, httpx; Python/Node không nằm trên PATH shell nên kiểm tra bằng đường dẫn thực tế.

## Phase 2–5: bản triển khai đầu tiên
- Hoàn thành naive, FC, MRV + Degree, LCV, MAC/AC-3 và Min-Conflicts.
- Tách hàm chọn biến, sắp giá trị, forward_check, revise, ac3 để dễ giải thích.
- MAC chạy AC-3 toàn cục ban đầu, rồi duy trì sau mỗi lần gán.
- Hoàn thành API, giao diện ba cột, border 3×3, màu action, log tự cuộn và replay bằng timer.
- Xóa bảng/tạo đề mẫu hủy phiên giao diện và bỏ response cũ; không giả vờ hủy được thread tính toán backend.
- Có tài liệu giải thích kiến trúc/thuật toán và câu hỏi bảo vệ.

## Kiểm thử vòng đầu
- Python: 47 test đạt, 1 test sai kỳ vọng số học (501 + 2 + 1 phải là 504, không phải 505); đã sửa kỳ vọng.
- Node: 4 test replay đạt; kiểm tra cú pháp app.js/replay.js đạt.
- Đang bổ sung kiểm tra tương tác bằng trình duyệt thực trước khi chốt kết quả.

## Kiểm chứng tích hợp và hoàn tất
- Python đã chạy lại: 48/48 test đạt.
- Trình duyệt thật phát hiện lỗi binding setTimeout (`Illegal invocation`); đã sửa wrapper globalThis, không chỉ dựa vào unit test timer giả.
- Sửa auto-scroll ở bước cuối khi layout đổi chiều cao; thêm requestAnimationFrame sau layout.
- Browser smoke chạy đạt: API thật, input, border, cảnh báo, replay, pause/resume, metrics, autoscroll, giải lại đề gốc, clear, 422 và responsive.
- Đã chụp và đọc lại ảnh desktop/mobile trong `docs/screenshots/`.
- Đã viết `docs/KIEM_THU.md` ghi kết quả, cách tái chạy và phạm vi chưa kiểm chứng.
- Đã hoàn thành năm phase chức năng. Các giới hạn tài nguyên, local search không đảm bảo và phạm vi 9×9 được ghi rõ trong tài liệu.