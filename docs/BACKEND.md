# Hiểu logic backend Sudoku CSP

Tài liệu đọc code và chuẩn bị bảo vệ, không yêu cầu hiểu frontend.
Đối chiếu với code ngày 17/10/2026. Dự án dùng cấu hình module,
**không còn sáu hàm giải hay trường request `algorithm`**.

## 1. Bức tranh tổng thể

Backend nhận bàn Sudoku và cấu hình, tìm **một nghiệm**, trả kết quả,
số liệu và lịch sử thao tác. Không kiểm tra tính duy nhất của nghiệm.

```text
POST /solve (hoặc /api/solve)
    ↓
SolveRequest: kiểm tra kiểu, kích thước, các cờ
    ↓
Endpoint lấy solve_lock
    ↓
SudokuCSPSolver.__init__: dựng peers, kiểm tra đề, tạo domains
    ↓
solve(): bật tracemalloc nếu cần
    ↓
_solve_recorded(): bắt đầu đồng hồ, chọn nhánh
    ├── backtracking
    │     ├── AC-3 toàn cục ban đầu nếu inference=ac3
    │     └── backtrack(): chọn ô → chọn số → suy diễn → đệ quy/khôi phục
    └── local_search
          └── solve_local_search(): điền kín → sửa ô xung đột → restart nếu kẹt
    ↓
Ghi SUCCESS/FAIL, chốt metrics, trả dict
    ↓
solve(): tắt tracer nếu chính nó đã bật; endpoint nhả lock
    ↓
SolveResponse: kiểm tra cấu trúc response → JSON
```

**Ba ý cần nhớ:**
1. MRV chọn **ô**, LCV chọn **thứ tự số**, FC/AC-3 làm **suy diễn**, CBJ quyết định **quay lui thế nào**.
2. `board` là số đã đặt; `domains` là khả năng còn lại. Domain chỉ còn một số **chưa có nghĩa** đã gán số đó lên board.
3. Local Search khác DFS về bản chất nên có vòng lặp riêng, không qua `backtrack()`.

## 2. Thứ tự đọc code

| Thứ tự | Đường dẫn tuyệt đối | Cần hiểu |
|---|---|---|
| 1 | `D:\Sudoku_Project_IntroAI\backend\models.py` | Dữ liệu vào/ra hợp lệ là gì |
| 2 | `D:\Sudoku_Project_IntroAI\backend\main.py` | HTTP dẫn vào solver thế nào |
| 3 | `D:\Sudoku_Project_IntroAI\backend\solver.py` | Đọc `__init__`, `solve`, `_solve_recorded`, `backtrack` trước, rồi các hook |
| 4 | `D:\Sudoku_Project_IntroAI\tests\test_solver.py` | Các hành vi đang được kiểm tra |

## 3. Contract API và validation

Hai endpoint dùng cùng hàm xử lý: `POST /solve` và `POST /api/solve`.
Ví dụ request hợp lệ, còn một ô trống:

```json
{
  "board": [
    [5,3,0,6,7,8,9,1,2],
    [6,7,2,1,9,5,3,4,8],
    [1,9,8,3,4,2,5,6,7],
    [8,5,9,7,6,1,4,2,3],
    [4,2,6,8,5,3,7,9,1],
    [7,1,3,9,2,4,8,5,6],
    [9,6,1,5,3,7,2,8,4],
    [2,8,7,4,1,9,6,3,5],
    [3,4,5,2,8,6,1,7,9]
  ],
  "base_algorithm": "backtracking",
  "inference": "fc",
  "use_mrv": true,
  "use_lcv": true,
  "backtrack_strategy": "standard"
}
```

| Trường | Giá trị | Mặc định nếu bỏ qua |
|---|---|---|
| `board` | Đúng 9 × 9, số nguyên 0–9; 0 là ô trống | Bắt buộc |
| `base_algorithm` | `backtracking`, `local_search` | Bắt buộc |
| `inference` | `none`, `fc`, `ac3` | `none` |
| `use_mrv` | Boolean JSON | `false` |
| `use_lcv` | Boolean JSON | `false` |
| `backtrack_strategy` | `standard`, `cbj` | `standard` |

- `StrictInt` không nhận `true`, `"1"`, `1.5` làm chữ số Sudoku.
- `StrictBool` không nhận chuỗi `"true"` hay số `1` làm cờ.
- `extra="forbid"` từ chối trường lạ, gồm trường `algorithm` cũ.
- Với `local_search`, solver bỏ qua các cờ còn lại. Nhưng nếu vẫn gửi những trường ấy,
  Pydantic **vẫn kiểm tra tính hợp lệ** trước khi vào solver.
- Sai schema trả HTTP 422. Đề trùng số cũng trả 422, nhưng được constructor phát hiện
  bằng `is_safe()`, sau đó endpoint chuyển `ValueError` thành `HTTPException`.
- Khi gọi Python trực tiếp, hãy dùng bàn hợp lệ và tạo config bằng `SolveRequest`;
  constructor solver không thay thế toàn bộ validation của Pydantic.

Response gồm `status`, `config_summary`, `metrics`, `history`.
Không còn `algorithm_used`. Bàn kết quả nằm trong `history[-1]["board_snapshot"]`.

## 4. Khởi tạo mô hình CSP

- **Biến:** 81 ô `X(r,c)`, chỉ số Python/JSON từ 0 đến 8.
- **Miền:** các số 1–9 không xung đột với đề cho trước.
- **Ràng buộc:** hai ô chung hàng, cột hoặc khối 3×3 phải khác nhau.

Một ô có 20 `peers` khác nhau. Tập hợp tránh đếm trùng các ô vừa chung hàng vừa chung khối.
Điều kiện cùng khối: `(a // 3, b // 3) == (r // 3, c // 3)`.

| Thuộc tính | Vai trò |
|---|---|
| `board` | Bản `deepcopy` đầu vào; 0 nghĩa chưa gán |
| `cells` | 81 tọa độ theo thứ tự hàng rồi cột |
| `locked_cells` | Các ô đề bài, không được sửa |
| `peers[cell]` | Các ô bị ràng buộc khác số với `cell` |
| `domains[cell]` | Danh sách giá trị; ô đề có miền singleton |
| `reasons[cell]` | Tập quyết định gây cắt miền, phục vụ CBJ |
| `history` | Các sự kiện, mỗi sự kiện có bản sao board riêng |
| `assignments`, `backtracks`, `prunes` | Bộ đếm tích lũy, không rollback |

`is_safe(r,c,val)` chỉ kiểm tra val khác số đã đặt tại các peers.
Nó không tự kiểm tra miền 1–9; phần đó do schema và cách tạo danh sách số đảm nhiệm.

### `domains` khác `available_values()` thế nào?

`domains` khởi tạo từ đề, sau đó FC/AC-3 thay đổi nó. Với `inference=none`,
không lan truyền sang miền láng giềng: domain có thể còn số bị phép gán mới làm xung đột.
`available_values(cell)` lọc domain bằng `is_safe()` theo board hiện tại,
**không sửa domain, không tăng prunes**. Nhờ vậy MRV/LCV vẫn dùng được khi tắt inference.

## 5. Bộ khung duy nhất: `backtrack()`

Code tổ chức theo tinh thần **Template Method + flags**: hàm điều phối có bộ khung cố định,
gọi các hook theo config. Không có hệ thống subclass/override của Template Method cổ điển;
cũng không phải State Machine được cài đặt bằng bảng trạng thái.

`backtrack()` trả **tuple `(solved, conflict_set)`**, không chỉ boolean.
`_solve_recorded()` lấy `self.backtrack()[0]` vì tuple `(False, set())` tự nó vẫn truthy trong Python.

### Bước 0–1: chọn ô và điều kiện dừng

- MRV tắt: `select_unassigned_variable()` lấy ô trống đầu tiên.
- MRV bật: `select_unassigned_variable_mrv()` chọn ô ít `available_values()` nhất.
- Hòa thì ưu tiên ô nhiều peers còn trống (**Degree**), cuối cùng theo tọa độ.
- Không còn ô trống: trả `(True, set())`. Với DFS, các phép gán trước đó đều qua `is_safe()`,
  nên board đầy là nghiệm. Không áp dụng lập luận này cho Local Search.

### Bước 2: thứ tự số

- LCV tắt: sao chép `domains[cell]`, thử theo thứ tự hiện có; vẫn kiểm tra `is_safe()` trước gán.
- LCV bật: `order_domain_values_lcv()` chấm điểm mỗi số an toàn bằng số peers chưa gán
  mà `available_values(peer)` chứa số ấy. Điểm thấp được thử trước, hòa thì số nhỏ trước.
- Đây là ước lượng tác động trực tiếp, không chạy thử toàn bộ AC-3 cho mỗi số.

### Bước 3: gán và suy diễn

Với mỗi số an toàn:
1. `deepcopy` cả `domains` và `reasons` **trước khi thay đổi**.
2. `assign()` đặt số lên board, tăng assignments, ghi ASSIGN.
3. Đặt miền ô đang xét thành `[val]`, nguyên nhân thành `{cell}`.
4. Gọi FC, AC-3 hoặc không suy diễn theo config.
5. Nhất quán thì gọi đệ quy; có nghiệm thì trả ngay.

### Bước 4: khôi phục và quay lui

Nếu nhánh thất bại:
1. Khôi phục `domains` và `reasons` từ bản sao.
2. `unassign()` đặt ô về 0, tăng backtracks, ghi BACKTRACK.
3. Standard thử số kế tiếp; CBJ xét nguyên nhân để có thể bỏ qua tầng hiện tại.
4. Hết số: trả thất bại cùng tập xung đột, loại các ô đề cố định.

**Vì sao restore cả miền lẫn nguyên nhân?** X=5 cắt 5 khỏi D(Y); bỏ X=5 phải trả lại 5
cho Y và xóa lý do “X đã cắt miền Y”. Quên restore nguyên nhân có thể khiến CBJ nhảy sai.
History/counters không restore vì phản ánh công sức đã bỏ ra ở cả nhánh sai.

Nếu `SearchLimit` xảy ra, exception thoát đệ quy để dừng ngay, không bảo đảm khôi phục
board/domains về đề gốc. Snapshot cuối có thể là trạng thái tìm kiếm dở.

## 6. Inference: FC và AC-3/MAC

### Forward Checking — `forward_check(r,c,val)`

Sau X=5, duyệt peers Y chưa gán. Nếu 5 thuộc D(Y), `prune()` xóa 5,
thêm X vào `reasons[Y]`, tăng prunes, ghi PRUNE. D(Y) rỗng thì trả `False` ngay.
FC chỉ nhìn ảnh hưởng trực tiếp của **phép gán mới**. D(Y) còn `[7]` không khiến
FC tự tiếp tục xóa 7 ở peers của Y.

### AC-3 — `revise(x,y)` và `ac3(queue)`

Cung `(X,Y)` yêu cầu mỗi số trong D(X) có ít nhất một số trong D(Y) khác nó.
Với `X != Y`, D(Y) có ít nhất hai số thì mọi số của X đều có hỗ trợ.
Nếu D(Y) chỉ còn `[5]`, phải xóa 5 khỏi D(X) nếu có.

`ac3()` lấy cung từ queue, gọi `revise()`. Nếu D(X) đổi:
- Miền rỗng → trả `False`.
- Ngược lại thêm các cung `(Z,X)`, với Z là peer của X và Z khác Y, để lan truyền tiếp.

Nguyên nhân từ Y được truyền sang X; nếu Y đã gán, thêm chính Y làm nguyên nhân.
Đây là `revise()` tối ưu riêng cho ràng buộc khác số, không phải bộ giải CSP tổng quát.

### MAC là cách dùng AC-3 trong tìm kiếm

Với `inference=ac3`, `_solve_recorded()` chạy AC-3 toàn bộ cung trước DFS.
Sau mỗi gán, `backtrack()` gọi AC-3 từ `(peer,cell)` để duy trì phù hợp cung.
Đó là **Maintaining Arc Consistency**, không phải solver đệ quy thứ hai.

Ví dụ với các quan hệ peer phù hợp: D(X)=[1], D(Y)=[1,2], D(Z)=[2,3].
AC-3 có thể làm Y còn [2], rồi Z còn [3] dù hai ô ấy vẫn chưa gán lên board.
FC sau X=1 chỉ cắt trực tiếp ở Y.

**Arc consistency không bảo đảm có nghiệm**, vẫn cần DFS. AC-3 trên ràng buộc nhị phân
cũng không mạnh bằng bộ lan truyền `AllDifferent` chuyên dụng.

## 7. CBJ: bỏ qua quyết định không gây lỗi

**CBJ đã có logic trong code, không phải placeholder.**

- `reasons[cell]` gom nguyên nhân cắt miền ở cấp ô, không lưu giải thích riêng từng giá trị.
- Khi xét một ô, solver gom thêm peers đã gán đang chặn các số trong domain.
- Inference tạo miền rỗng: gom reasons các miền rỗng thành `causes`.
- Đệ quy thất bại: nhận `causes` từ tầng sâu.
- Sau rollback, nếu bật CBJ và `cell not in causes`, đổi số của ô này không xử lý
  nguyên nhân vừa nhận: trả thất bại ngay, không thử các số khác ở tầng đó.
- Nếu ô hiện tại có trong causes, tiếp tục thử số khác và gom `causes - {cell}`.

Ví dụ ngăn xếp `A → B → C → D`, lỗi ở D chỉ phụ thuộc A và B.
C nhận causes không chứa C, xóa gán C và trả ngay; B có trong causes nên thử số khác.
“Nhảy” được hiện thực bằng trả về qua các frame đệ quy, không sửa trực tiếp con trỏ tầng.

Tập nguyên nhân cấp ô có thể rộng hơn tối thiểu nên không bảo đảm nhảy xa nhất.
Đây không phải conflict learning: code không lưu nogood dùng cho các nhánh tương lai.

Một tầng bị bỏ qua có BACKTRACK xóa ô (`cell` có tọa độ), rồi BACKTRACK thông báo CBJ
(`cell=null`). Counter chỉ tăng tại `unassign()`; **không đếm mọi dòng BACKTRACK** để suy ra counter.

## 8. Local Search — Min-Conflicts

`solve_local_search()` không dùng domains, MRV, LCV, inference hay CBJ.

1. Lấy các ô `mutable` không thuộc đề; điền ngẫu nhiên 1–9 để board đầy.
2. Mỗi vòng lấy ngẫu nhiên một ô đang xung đột.
3. Chấm `conflict_count(cell,val)` với từng số 1–9; chọn số ít peers cùng số nhất,
   phá hòa ngẫu nhiên, rồi gán lại.
4. Hết xung đột → thành công.
5. Sau 500 bước không cải thiện điểm tốt nhất kể từ khởi tạo/restart, khởi tạo lại các ô mutable.
6. Hết tổng 10.000 vòng sửa → `not_found`, trừ khi board cuối đã hết xung đột.

`total_conflicts()` đếm cạnh peers có hai đầu cùng số rồi chia 2 vì mỗi cạnh bị duyệt hai lần.
Đổi một ô chỉ ảnh hưởng cạnh nối ô đó: tối thiểu lỗi cục bộ tương đương tối thiểu tổng lỗi
khi các ô khác cố định, không phải tối ưu toàn cục có bảo đảm.

Restart không reset ngân sách vòng lặp, đồng hồ hay counters; ô đề không bị sửa.
`seed` giúp tái hiện ngẫu nhiên khi tạo solver trực tiếp; API chưa có trường seed.
Không có fallback DFS để làm Local Search trông như luôn giải được.

## 9. Metrics đo chính xác điều gì?

| Trường | Cách đo/đếm |
|---|---|
| `execution_time_ms` | `(perf_counter() - started) * 1000`, bắt đầu ở `_solve_recorded()` |
| `peak_memory_kb` | Peak của `tracemalloc.get_traced_memory()[1] / 1024` |
| `total_assignments` | Mỗi gán thử DFS; Local Search tính từng ô điền khi khởi tạo/restart và mỗi gán sửa |
| `total_backtracks` | Mỗi lần `unassign()` đặt ô về 0, gồm rollback qua tầng CBJ |
| `total_prunes` | Mỗi lần `prune()` xóa một giá trị khỏi một domain |

- `is_safe()` từ chối một số không tăng assignments; số đề không tính là gán tìm kiếm.
- Local Search có thể chọn lại số cũ: code vẫn thực hiện gán và tăng assignments.
- Khởi tạo/restart ghi một ASSIGN (`cell=null`) nhưng tăng assignments theo số ô mutable.
- Cắt cùng số ở các nhánh khác nhau được đếm nhiều lần; restore không trừ prunes.
- Tạo domain ban đầu, lọc `available_values()` và đặt domain ô vừa gán thành `[val]` không tăng prunes.

### Ranh giới phép đo

Constructor chạy **trước** `solve()`: tạo peers, kiểm tra đề, tạo domains không nằm trong thời gian giải;
khi solver tự bật tracer, cấp phát constructor cũng không nằm trong peak.
Phép đo tính tìm kiếm, deepcopy nhánh, ghi history và AC-3 ban đầu.
Không tính chờ lock, truyền mạng, validation/serialization response sau khi solver trả về.

`tracemalloc` đo cấp phát Python, **không phải RSS/toàn bộ RAM hệ điều hành**.
Tracer dùng chung toàn tiến trình. `solve_lock` tuần tự hóa các request giải trong một process,
nhưng không cô lập được cấp phát của hoạt động khác trong process.
Nếu caller đã bật tracer, solver không reset peak/không tắt tracer ấy: số đo có thể gồm cấp phát từ trước.
Gọi solver trực tiếp không tự lấy endpoint lock.

Đây là metrics minh họa chi phí có đo bộ nhớ/ghi history, không phải benchmark thuần CSP.
MRV/LCV ít nhánh hơn vẫn có thể tốn thời gian hơn vì chi phí chọn/sắp xếp.

## 10. History, trạng thái và ngân sách

`record_step()` lưu `step`, `action`, `cell`, `value`, `board_snapshot`, `log`, `metrics`.
Snapshot `deepcopy` giữ quá khứ độc lập. Tọa độ JSON từ 0; log thường hiển thị từ 1.

| Action | Ý nghĩa |
|---|---|
| `ASSIGN` | Board đã có số mới |
| `PRUNE` | Đã cắt domain; board có thể không đổi; `value=null`, số bị cắt nằm trong log |
| `BACKTRACK` | Đã xóa gán (`value=0`) hoặc thông báo CBJ (`cell=null`) |
| `SUCCESS` | Kết thúc tìm được nghiệm |
| `FAIL` | Kết thúc không thành công; phải xem thêm status |

Domains/reasons không gửi ra: không thể khôi phục đầy đủ miền chỉ từ board snapshots.
Metrics bước cuối được cập nhật bằng metrics tổng để hai nơi khớp nhau.

| Status | Diễn giải |
|---|---|
| `success` | Tìm được một nghiệm |
| `unsolvable` | DFS/suy diễn chứng minh không có nghiệm, không bị ngắt ngân sách |
| `not_found` | Local Search hết số vòng, chưa tìm được; không kết luận vô nghiệm |
| `limit_reached` | Chạm giới hạn thời gian/history; không kết luận vô nghiệm |

Mặc định 15 giây vòng tính toán, 30.000 sự kiện thường.
`check_budget()` kiểm tra tại nhiều điểm, không ngắt cưỡng bức đúng mốc 15 giây.
SUCCESS/FAIL được miễn kiểm tra nên history có thể dài **30.001** phần tử.
HTTP có thể vượt 15 giây vì chờ lock, xử lý ngoài vòng giải và serialize.

## 11. Truy vết một ô trống — tự kiểm tra không cần frontend

Với request ở mục 3:
1. Constructor tạo D((0,2))=[4], ô trống duy nhất.
2. MRV chọn ô ấy; LCV trả [4].
3. Sao lưu miền/nguyên nhân; gán 4, tăng assignments thành 1, ghi ASSIGN.
4. FC không cắt gì vì mọi peer đã gán.
5. Đệ quy không còn ô trống → thành công, ghi SUCCESS.
6. Counter cuối: 1 assignment, 0 backtracks, 0 prunes; có 2 sự kiện.

Khởi động bằng PowerShell:

```powershell
cd D:\Sudoku_Project_IntroAI
& D:\Sudoku_Project_IntroAI\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload
```

Mở `http://127.0.0.1:8000/docs`, chọn `POST /solve`, dán nguyên JSON mục 3 rồi Execute.
Đổi sang `local_search` để thấy nhánh giải khác; cờ còn lại không tác động nhánh đó.

## 12. Giải thích với giảng viên

**Bài giới thiệu ngắn:**
“Em mô hình Sudoku thành CSP gồm biến, miền và ràng buộc khác số giữa các peers.
Backend có bộ khung DFS `backtrack()` dùng các hook MRV, LCV, FC hoặc AC-3 theo flags.
Mỗi nhánh sao lưu/phục hồi miền và nguyên nhân tại một nơi. CBJ bỏ qua quyết định không liên quan.
Min-Conflicts là nhánh riêng vì làm việc trên phép gán đầy đủ. Kết quả kèm lịch sử và metrics.”

**Không inference có phải không dùng domain?** Không. Vẫn có miền khởi tạo và singleton
cho ô đang thử; chỉ không lan truyền cắt miền sang láng giềng.

**AC-3 có tự điền singleton?** Không, nó cắt domain; DFS sau đó mới ghi gán lên board.

**Vì sao vẫn `is_safe()` với FC/MAC?** Để dùng một lớp kiểm tra chung cho mọi cấu hình,
đặc biệt khi tắt suy diễn. Không phải nhìn domain là an toàn ở mọi chế độ.

**Thêm Degree Heuristic?** Hiện Degree đã phá hòa MRV. Muốn bật/tắt độc lập thì thêm config,
đổi hook chọn biến, không tạo một solver mới.

**Độ phức tạp?** Cận thô DFS O(9^E) với E ô trống, chưa tính chi phí mỗi nút.
Heuristics/propagation giảm tìm kiếm thực tế, không bảo đảm tránh bùng nổ tổ hợp.
History lưu O(81 × H) ô với H sự kiện, cộng các bản sao domains/reasons theo độ sâu đệ quy.

**CBJ luôn tốt hơn Standard?** Không, có chi phí theo dõi nguyên nhân; không phải đề nào
cũng có nhiều tầng không liên quan để bỏ qua.

## 13. Giới hạn và tình trạng kiểm chứng

- Chỉ 9×9, một nghiệm; chưa kiểm tra nghiệm duy nhất.
- Lock theo process, không phải hàng đợi phân tán/sandbox. Không có rate limit hay giới hạn RAM cứng;
  chưa phù hợp mở trực tiếp ra Internet.
- Một instance solver nên dùng một lần: gọi `solve()` lần nữa không reset board/history/counters.
- Log cũ `D:\Sudoku_Project_IntroAI\.pytest-refactor.log`: **158 đạt, 4 thất bại**.
  Bốn cấu hình đề mẫu không inference, không MRV trả `limit_reached` thay vì `success`.
  Không được từ đó khẳng định toàn bộ test đạt hoặc solver trả nghiệm sai.
- Lần cập nhật docs chạy nhóm backend/API chọn lọc: **58 đạt, 104 không được chọn**, không phải toàn suite.
  Xem `D:\Sudoku_Project_IntroAI\docs\KIEM_THU.md` để biết phạm vi.