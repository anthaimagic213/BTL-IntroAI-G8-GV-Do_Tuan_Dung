# Hướng dẫn chạy dự án Sudoku CSP Algorithm Visualizer

[← Trang chủ](../README.md) · [Tổng quan thuật toán](TONG_QUAN_THUAT_TOAN.md)

## 1. Chuẩn bị

- Python có hỗ trợ môi trường ảo `venv` (dự án đã được kiểm chứng với Python 3.12).
- Git để clone repo; nếu đã có mã nguồn thì chỉ cần mở terminal ở thư mục chứa `requirements.txt`.
- Trình duyệt để sử dụng giao diện. **Không cần Node.js/npm để chạy ứng dụng**; Node.js chỉ dùng khi chạy test JavaScript.

Các lệnh dưới đây dùng **Windows PowerShell**. `py` có thể thay bằng `python` hoặc đường dẫn tới Python đã cài nếu không có Python Launcher.

## 2. Lấy mã nguồn và cài dependency

```powershell
git clone https://github.com/anthaimagic213/BTL-IntroAI-G8-GV-Do_Tuan_Dung.git
cd BTL-IntroAI-G8-GV-Do_Tuan_Dung
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Nếu đã clone repo, bỏ qua `git clone`, `cd` vào thư mục repo rồi thực hiện hai lệnh cuối. Chạy các lệnh tiếp theo **tại thư mục gốc dự án** (nơi có `backend/`, `frontend/` và `requirements.txt`). Cách gọi trực tiếp `.venv\Scripts\python.exe` không yêu cầu kích hoạt môi trường ảo hay thay đổi execution policy của PowerShell.

## 3. Khởi động

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Truy cập **http://127.0.0.1:8000** để mở ứng dụng; **http://127.0.0.1:8000/docs** là Swagger API. Dùng `Ctrl+C` trong terminal để dừng server. Không mở `frontend/index.html` bằng `file://`: frontend cần gửi request tới API và tải tài nguyên qua cùng server.

## 4. Sử dụng giao diện

1. Nhập các số từ 1–9 vào bảng hoặc chọn **Tạo đề mẫu**; dùng Backspace/Delete để xóa ô.
2. Chọn **Backtracking Search (DFS)**, tùy chọn `none`/FC/AC-3, MRV, LCV, Standard/CBJ; hoặc chọn **Local Search (Min-Conflicts)**. Local Search không sử dụng các tùy chọn của DFS.
3. Nhấn **Giải Sudoku**. Backend giải xong rồi frontend mới phát lại các bước; quan sát bảng, màu, log và metrics.
4. Dùng **Tạm dừng / Tiếp tục** và thanh tốc độ (1–1000 ms/bước) để xem replay. Tạm dừng chỉ dừng phát lại, không tạm dừng phép giải trên backend.
5. Có thể **Xóa bảng**, **Tạo đề mẫu** hoặc **Giải lại đề gốc** để thử cấu hình khác. Nếu sửa trực tiếp bảng kết quả, nội dung hiện tại sẽ trở thành đề mới.

Chỉ hỗ trợ bảng 9×9; `0` biểu thị ô trống trong API. Schema yêu cầu `base_algorithm` là `backtracking` hoặc `local_search`; chi tiết các trường cấu hình và ví dụ JSON ở [tài liệu backend](BACKEND.md#3-contract-api-và-validation).

## 5. Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Nếu đã cài Node.js và muốn chạy thêm test bộ lập lịch phát lại:

```powershell
node --test tests/replay.test.mjs
```

Test trình duyệt thật là tùy chọn: xem [tài liệu kiểm thử](KIEM_THU.md). **Lưu ý:** tài liệu này ghi nhận một lần chạy toàn bộ test trước đây có 4 ca không đạt vì cấu hình DFS không inference/MRV chạm giới hạn thời gian; không nên mặc định toàn bộ suite luôn xanh.

## 6. Lỗi thường gặp

| Hiện tượng | Cách kiểm tra |
|---|---|
| `py` không tồn tại | Dùng `python -m venv .venv` hoặc đường dẫn Python trên máy. |
| Không tìm thấy `backend` hoặc `requirements.txt` | Kiểm tra terminal đang ở thư mục gốc repo. |
| Cổng 8000 đã được dùng | Dừng tiến trình đang chiếm cổng hoặc thêm `--port 8001` vào lệnh Uvicorn rồi mở `http://127.0.0.1:8001`. |
| API trả 422 | Kiểm tra bàn có đúng 9×9 số nguyên 0–9, không trùng số đề trong hàng/cột/khối và trường cấu hình đúng schema. |
| Kết quả `limit_reached` hoặc `not_found` | Đây không nhất thiết là đề vô nghiệm; xem [ý nghĩa trạng thái](TONG_QUAN_THUAT_TOAN.md#trạng-thái-kết-quả-và-giới-hạn). |

[← Trang chủ](../README.md)