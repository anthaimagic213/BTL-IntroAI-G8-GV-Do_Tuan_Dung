# Kiến trúc backend và chuẩn bị bảo vệ

Hướng dẫn hiện hành đã được tổ chức lại tại:

**`D:\Sudoku_Project_IntroAI\docs\BACKEND.md`**

Đọc theo thứ tự:

1. Mục 1–4: luồng request, vai trò từng file, contract và mô hình CSP.
2. Mục 5: bộ khung `backtrack()` dùng chung và sao lưu/phục hồi trạng thái.
3. Mục 6–8: FC, AC-3/MAC, CBJ và Min-Conflicts.
4. Mục 9–11: ý nghĩa metrics, history, trạng thái và ví dụ truy vết.
5. Mục 12–13: bài trình bày ngắn, câu hỏi bảo vệ và giới hạn thực tế.

Không cần đọc code frontend để hiểu các phần trên.

## Đối chiếu lý thuyết CSP trong bài giảng

- Trang 3–7: biến, miền giá trị, ràng buộc và đồ thị CSP.
- Trang 15–17: tìm kiếm DFS/quay lui.
- Trang 26–28: MRV, Degree phá hòa và LCV.
- Trang 29: Forward Checking.
- Trang 34–39: phù hợp cung, AC-3 và lan truyền ràng buộc.
- Trang 40–41: Local Search/Min-Conflicts.

CBJ được giải thích theo code hiện tại trong tài liệu backend; danh sách trên
không khẳng định bài giảng có trình bày đầy đủ phần CBJ.

## Những thông tin cũ không còn áp dụng

- Không gửi `algorithm: "fc_mrv"`; dùng các cờ module trong `SolveRequest`.
- Không có sáu solver đệ quy độc lập; chỉ có một `backtrack()`.
- Response dùng `config_summary`, không dùng `algorithm_used`.
- Metrics dùng `total_assignments`, `total_backtracks`, `total_prunes`.
- CBJ có logic thực thi, không phải placeholder.
- Không khẳng định toàn bộ test sau refactor đã đạt. Phạm vi kiểm chứng và kết quả
  thực tế nằm tại `D:\Sudoku_Project_IntroAI\docs\KIEM_THU.md`.