# Sudoku CSP Algorithm Visualizer

> Bài tập lớn Nhập môn Trí tuệ nhân tạo: giải Sudoku 9×9 và trực quan hóa quá trình tìm nghiệm bằng các kỹ thuật thỏa mãn ràng buộc (CSP).

Ứng dụng cho phép chọn **Backtracking (DFS)** với các tùy chọn suy diễn, heuristic và chiến lược quay lui; hoặc **Local Search (Min-Conflicts)** để so sánh cách tiếp cận. Backend FastAPI giải bài toán và ghi lại từng trạng thái; frontend HTML/CSS/JavaScript phát lại lịch sử cùng log và số liệu (**Record & Replay**). Chạy ứng dụng không cần npm hay bước build frontend.

**Mã nguồn:** [GitHub — BTL-IntroAI-G8-GV-Do_Tuan_Dung](https://github.com/anthaimagic213/BTL-IntroAI-G8-GV-Do_Tuan_Dung.git)

## Bắt đầu từ đâu?

| Bạn muốn... | Tài liệu |
|---|---|
| Clone repo, cài môi trường, chạy ứng dụng, dùng giao diện và chạy test | [Hướng dẫn chạy dự án](docs/CHAY_DU_AN.md) |
| Nắm toàn cảnh CSP, các thuật toán/kỹ thuật và cách chúng phối hợp | [Tổng quan thuật toán và kiến thức](docs/TONG_QUAN_THUAT_TOAN.md) |
| Theo dõi request, đọc từng hàm solver, truy vết ví dụ và chuẩn bị bảo vệ | [Giải thích backend chi tiết](docs/BACKEND.md) |
| Đối chiếu nội dung với bài giảng và xem gợi ý bảo vệ | [Kiến trúc và bảo vệ](docs/KIEN_TRUC_VA_BAO_VE.md) |
| Xem phạm vi/kết quả kiểm chứng và hướng dẫn test trình duyệt | [Kiểm thử](docs/KIEM_THU.md) |
| Xem tiến độ thực hiện | [Tiến độ](docs/TIEN_DO.md) |

**Chạy nhanh trên Windows PowerShell** (đã cài Python và Git):

```powershell
git clone https://github.com/anthaimagic213/BTL-IntroAI-G8-GV-Do_Tuan_Dung.git
cd BTL-IntroAI-G8-GV-Do_Tuan_Dung
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Mở [giao diện](http://127.0.0.1:8000) hoặc [Swagger API](http://127.0.0.1:8000/docs). Nếu máy không có lệnh `py`, thay bằng `python`. Xem [hướng dẫn đầy đủ](docs/CHAY_DU_AN.md) để biết cách thao tác, kiểm thử và xử lý lỗi thường gặp.

## Bản đồ mã nguồn

- [`backend/models.py`](backend/models.py): kiểm tra request và định dạng response.
- [`backend/main.py`](backend/main.py): API `POST /solve` (alias `POST /api/solve`) và phục vụ giao diện.
- [`backend/solver.py`](backend/solver.py): CSP, DFS, FC/AC-3, MRV/LCV, CBJ, Min-Conflicts và ghi lịch sử.
- [`frontend/`](frontend/): giao diện, gọi API và phát lại các snapshot.
- [`tests/`](tests/): kiểm thử backend/API và bộ phát lại.

**Phạm vi:** chỉ Sudoku 9×9, tìm một nghiệm chứ không kiểm tra tính duy nhất. Local Search có thể chưa tìm ra nghiệm trong ngân sách; thời gian và bộ nhớ hiển thị gồm cả chi phí ghi lịch sử, không phải benchmark thuần thuật toán. Xem [tổng quan kỹ thuật](docs/TONG_QUAN_THUAT_TOAN.md) để hiểu các giới hạn này.