# Tổng quan thuật toán và kiến thức xử lý Sudoku

[← Trang chủ](../README.md) · [Hướng dẫn chạy](CHAY_DU_AN.md) · [Đọc code backend chi tiết](BACKEND.md)

Tài liệu này tóm tắt **bài toán, ý tưởng, quy trình và vai trò từng kỹ thuật**. Để xem từng hàm, tập nguyên nhân, ví dụ truy vết và contract API, đọc tiếp [BACKEND.md](BACKEND.md).

## 1. Từ Sudoku đến bài toán CSP

Sudoku 9×9 được biểu diễn bằng **81 biến** (các ô), **miền giá trị** là các số 1–9 khả dĩ, và **ràng buộc**: hai ô cùng hàng, cột hoặc khối 3×3 không được bằng nhau. Mỗi ô có tập `peers` gồm các ô liên quan; số cho trước là ô cố định, không được sửa. Trong `board`, `0` nghĩa là chưa gán. Backend từ chối đề có các số cho trước trùng nhau và khởi tạo miền theo đề.

Điểm cần phân biệt: `board` lưu số **đã gán**, còn `domains` lưu **ứng viên**. Một miền trở thành `[v]` sau suy diễn không có nghĩa solver đã điền `v` lên bảng; DFS vẫn phải thực hiện phép gán. Khi không bật suy diễn, `available_values()` vẫn lọc ứng viên theo bảng hiện tại để MRV/LCV hoạt động đúng.

## 2. Hai hướng giải khác nhau

| Hướng giải | Trạng thái làm việc | Ý tưởng | Kết quả khi hết ngân sách |
|---|---|---|---|
| Backtracking (DFS) | Bảng điền từng phần, các miền ứng viên | Thử số an toàn, suy diễn rồi đi sâu; sai thì khôi phục và thử nhánh khác | `limit_reached`: chưa kết luận vô nghiệm |
| Local Search (Min-Conflicts) | Bảng được điền kín kể cả khi còn xung đột | Đổi giá trị của ô không cố định để giảm số xung đột | `not_found` nếu hết vòng lặp mà chưa có nghiệm; giới hạn thời gian/history có thể cho `limit_reached` |

DFS là một bộ khung dùng chung, cấu hình bằng `base_algorithm`, `inference`, `use_mrv`, `use_lcv`, `backtrack_strategy` (không có sáu hàm giải độc lập hay trường `algorithm`). Local Search là nhánh riêng, bỏ qua inference, MRV/LCV và CBJ.

## 3. Bộ khung Backtracking: chọn → thử → suy diễn → quay lui

1. Chọn một ô trống: ô đầu tiên theo thứ tự hàng/cột, hoặc dùng **MRV**.
2. Xác định thứ tự thử các số: thứ tự miền hiện tại, hoặc dùng **LCV**.
3. Với số không xung đột với bảng (`is_safe`), sao lưu `domains` và `reasons`, gán số và ghi sự kiện `ASSIGN`.
4. Tùy cấu hình, không suy diễn, chạy **Forward Checking**, hoặc duy trì **Arc Consistency** bằng AC-3. Miền rỗng báo nhánh hiện tại không thể tiếp tục.
5. Nếu nhất quán, đệ quy. Nếu nhánh thất bại, phục hồi miền/nguyên nhân, xóa phép gán và ghi `BACKTRACK`; **Standard** tiếp tục thử số khác, **CBJ** có thể bỏ qua tầng không liên quan.
6. Hết ô trống là tìm được nghiệm. Duyệt cạn mọi lựa chọn hợp lệ mà không bị giới hạn mới có thể kết luận `unsolvable`.

Lịch sử và các bộ đếm không được rollback: chúng ghi nhận cả công sức ở những nhánh sai. Cận thô của không gian thử là `O(9^E)` với `E` ô trống, chưa tính chi phí xử lý mỗi nhánh; heuristic và suy diễn giảm tìm kiếm thực tế chứ không bảo đảm thời gian luôn nhanh.

## 4. Các kỹ thuật áp dụng ở đâu?

| Kỹ thuật | Câu hỏi nó trả lời | Cách triển khai ở dự án |
|---|---|---|
| **MRV** (Minimum Remaining Values) | Chọn **ô nào**? | Ô trống ít giá trị hợp lệ nhất; hòa thì ưu tiên **Degree** (nhiều peer còn trống), sau đó thứ tự tọa độ. Degree là cách phá hòa, không có nút bật riêng. |
| **LCV** (Least Constraining Value) | Thử **số nào trước**? | Đếm số peer chưa gán còn có thể nhận số đó; điểm thấp hơn được thử trước. Đây là ước lượng trực tiếp, không giả lập AC-3 cho từng số. |
| **Forward Checking (FC)** | Phép gán vừa rồi loại số nào ở láng giềng? | Xóa giá trị mới gán khỏi miền các peer chưa gán; dừng khi miền rỗng. Không lan truyền tiếp chỉ vì một peer còn miền đơn. |
| **AC-3 / MAC** | Các miền có còn phù hợp theo từng cung không? | `revise(X,Y)` loại giá trị của `X` không có hỗ trợ trong `Y`; với ràng buộc khác số, chỉ cần xóa `v` khỏi `D(X)` khi `D(Y)=[v]`. Chạy AC-3 trên các cung ban đầu và sau mỗi phép gán (MAC). |
| **Standard backtracking** | Khi nhánh thất bại, quay lại đâu? | Trở về ô vừa gán và thử ứng viên tiếp theo. |
| **CBJ** (Conflict-Directed Backjumping) | Tầng quyết định nào gây thất bại? | Ghi tập nguyên nhân cắt miền; khi lỗi không liên quan đến ô hiện tại, trả tập xung đột về tầng trước thay vì thử hết các giá trị ở tầng này. |

Ví dụ: gán `X=5`; FC chỉ xóa `5` khỏi miền các peer của X. AC-3 có thể lan truyền tiếp nếu một peer Y sau đó chỉ còn `[7]`, khiến `7` bị loại ở các peer của Y, **nhưng chưa tự điền Y=7 lên board**. CBJ có thể bỏ qua một quyết định C nếu lỗi ở tầng sâu chỉ do A và B gây ra. Nó không lưu “nogood” cho những nhánh tương lai, và không phải lúc nào cũng nhanh hơn Standard.

Không dùng inference **không đồng nghĩa** bỏ qua kiểm tra ràng buộc: mọi số trước khi gán vẫn phải qua `is_safe()`. AC-3 chỉ bảo đảm phù hợp cung, không tự chứng minh Sudoku có nghiệm; dự án cũng không dùng bộ lan truyền `AllDifferent` tổng quát.

## 5. Local Search: Min-Conflicts

1. Điền ngẫu nhiên 1–9 cho tất cả ô không cố định; các ô đề bài vẫn giữ nguyên.
2. Chọn ngẫu nhiên một ô đang xung đột. Thử đánh giá từng số 1–9 bằng số peer mang cùng số; chọn số có ít xung đột nhất, phá hòa ngẫu nhiên.
3. Lặp tới khi không còn xung đột. Nếu 500 bước không cải thiện mức tốt nhất thì khởi tạo lại các ô có thể sửa; ngân sách toàn cục **không reset**.
4. Mặc định tối đa 10.000 vòng sửa. Hết vòng mà vẫn xung đột trả `not_found`, **không** phải chứng minh đề vô nghiệm và không có fallback DFS.

Khác DFS, Min-Conflicts có thể đi qua các bảng sai tạm thời để tiến tới bảng hết xung đột; nó không dùng `domains` hay các phép PRUNE/BACKTRACK của DFS. Có yếu tố ngẫu nhiên nên kết quả có thể khác giữa các lần chạy.

## 6. Record & Replay: quan sát chứ không giải lại

Backend FastAPI nhận bảng/cấu hình qua `POST /solve` (`POST /api/solve` là alias), chạy solver và trả `status`, `config_summary`, `metrics`, `history`. Mỗi bước trong history có hành động (`ASSIGN`, `PRUNE`, `BACKTRACK`, `SUCCESS`, `FAIL`), log và một bản sao độc lập của bảng; `PRUNE` có thể không đổi bảng vì nó chỉ thay miền. Frontend nhận lịch sử rồi phát từng snapshot bằng timer; thay tốc độ hoặc tạm dừng **không** thay đổi kết quả backend.

Metrics gồm thời gian chạy backend, peak cấp phát Python đo bằng `tracemalloc`, số lần gán, quay lui và số giá trị bị cắt. Phép đo có chi phí lưu snapshot và không bao gồm thời gian phát animation; không nên coi đây là benchmark thuần tìm kiếm. Các bộ đếm là tích lũy, kể cả nhánh đã rollback.

## Trạng thái kết quả và giới hạn

| Status | Cách hiểu |
|---|---|
| `success` | Đã tìm thấy một nghiệm. |
| `unsolvable` | DFS/suy diễn hoàn tất mà không tìm được nghiệm, không bị ngắt bởi giới hạn. |
| `not_found` | Local Search hết số vòng mà chưa tìm thấy nghiệm. |
| `limit_reached` | Chạm giới hạn thời gian hoặc số sự kiện history; chưa kết luận vô nghiệm. |

Chỉ hỗ trợ Sudoku 9×9 và tìm **một** nghiệm, không kiểm tra nghiệm duy nhất. Mặc định giới hạn 15 giây vòng tính toán và 30.000 sự kiện thông thường (sự kiện kết thúc vẫn có thể được ghi); đây không phải giới hạn RAM cứng hay cam kết thời gian HTTP tối đa. Tìm hiểu sâu hơn tại [giải thích backend](BACKEND.md), [kiểm thử và các ca chưa đạt](KIEM_THU.md), và [đối chiếu bài giảng](KIEN_TRUC_VA_BAO_VE.md).

[← Trang chủ](../README.md)