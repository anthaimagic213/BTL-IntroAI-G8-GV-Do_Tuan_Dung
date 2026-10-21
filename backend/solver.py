"""Các thuật toán CSP độc lập với HTTP và giao diện.

Mỗi sự kiện sở hữu bản sao board: thay đổi tương lai không sửa quá khứ.
Domains là trạng thái tìm kiếm, không phải dữ liệu để frontend tự giải.
"""

from collections import deque
from copy import deepcopy
import random
from time import perf_counter
import tracemalloc

from backend.models import SolveRequest


class SearchLimit(Exception):
    """Dừng có kiểm soát, KHÔNG phải chứng minh vô nghiệm."""


class SudokuCSPSolver:
    def __init__(self, board, config=None, *, seed=None, max_steps=10_000,
                 max_history=30_000, timeout_seconds=15):
        self.board = deepcopy(board)
        self.config = config or SolveRequest(board=board, base_algorithm="backtracking")
        self.cells = [(r, c) for r in range(9) for c in range(9)]
        self.locked_cells = {(r, c) for r, c in self.cells if board[r][c]}
        self.peers = {
            (r, c): {(a, b) for a, b in self.cells
                     if (a, b) != (r, c) and
                     (a == r or b == c or (a // 3, b // 3) == (r // 3, c // 3))}
            for r, c in self.cells
        }
        if any(not self.is_safe(r, c, self.board[r][c])
               for r, c in self.locked_cells):
            raise ValueError("Đề bài có số trùng trong hàng, cột hoặc khối 3×3.")
        self.domains = {
            (r, c): [board[r][c]] if board[r][c] else
            [v for v in range(1, 10) if self.is_safe(r, c, v)]
            for r, c in self.cells
        }
        self.history = []
        # Các quyết định đã gây cắt miền; phục hồi cùng domains khi quay lui.
        self.reasons = {cell: set() for cell in self.cells}
        self.assignments = 0
        self.backtracks = 0
        self.prunes = 0
        self.random = random.Random(seed)
        self.max_steps = max_steps
        self.max_history = max_history
        self.timeout_seconds = timeout_seconds
        self.started = perf_counter()
        self.peak_memory_kb = 0

    def metrics(self):
        if tracemalloc.is_tracing():
            self.peak_memory_kb = max(self.peak_memory_kb, tracemalloc.get_traced_memory()[1] / 1024)
        return {
            "execution_time_ms": round((perf_counter() - self.started) * 1000, 3),
            "peak_memory_kb": round(self.peak_memory_kb, 2),
            "total_assignments": self.assignments,
            "total_backtracks": self.backtracks,
            "total_prunes": self.prunes,
        }

    def check_budget(self):
        if len(self.history) >= self.max_history:
            raise SearchLimit("Đã đạt giới hạn số sự kiện history.")
        if perf_counter() - self.started >= self.timeout_seconds:
            raise SearchLimit("Đã đạt giới hạn thời gian tính toán.")

    def record_step(self, action, r=None, c=None, val=None, log=""):
        # Chừa quyền ghi sự kiện kết thúc ngay cả khi đã hết ngân sách.
        if action not in ("SUCCESS", "FAIL"):
            self.check_budget()
        self.history.append({
            "step": len(self.history) + 1, "action": action,
            "cell": [r, c] if r is not None else None, "value": val,
            "board_snapshot": deepcopy(self.board), "log": log,
            "metrics": self.metrics(),
        })

    def is_safe(self, r, c, val):
        return all(self.board[a][b] != val for a, b in self.peers[(r, c)])

    def select_unassigned_variable(self):
        return next(((r, c) for r, c in self.cells if self.board[r][c] == 0), None)

    def select_unassigned_variable_mrv(self):
        empty = [(r, c) for r, c in self.cells if self.board[r][c] == 0]
        # MRV trước, Degree giảm dần phá hòa, cuối cùng thứ tự hàng/cột.
        return min(empty, key=lambda cell: (
            len(self.available_values(cell)),
            -sum(self.board[a][b] == 0 for a, b in self.peers[cell]), cell
        ), default=None)

    def order_domain_values_lcv(self, r, c):
        return sorted(self.available_values((r, c)), key=lambda val: (
            sum(val in self.available_values(p) for p in self.peers[(r, c)]
                if self.board[p[0]][p[1]] == 0), val))

    def assign(self, r, c, val, label):
        self.check_budget()
        self.board[r][c] = val
        self.assignments += 1
        self.record_step("ASSIGN", r, c, val,
                         f"[{label}] Gán {val} vào ô ({r + 1},{c + 1}).")

    def unassign(self, r, c):
        self.check_budget()
        self.board[r][c] = 0
        self.backtracks += 1
        self.record_step("BACKTRACK", r, c, 0,
                         f"Ngõ cụt: xóa giá trị tại ({r + 1},{c + 1}), quay lui.")

    def available_values(self, cell):
        # MRV/LCV vẫn đúng khi không bật propagation, không sửa domains.
        return [v for v in self.domains[cell] if self.is_safe(*cell, v)]

    def prune(self, cell, val, label, causes=()):
        self.check_budget()
        self.domains[cell].remove(val)
        self.reasons[cell].update(causes)
        self.prunes += 1
        r, c = cell
        self.record_step("PRUNE", r, c, None,
                         f"{label}: xóa {val} khỏi domain ({r + 1},{c + 1}).")

    def forward_check(self, r, c, val):
        for peer in sorted(self.peers[(r, c)]):
            if self.board[peer[0]][peer[1]] == 0 and val in self.domains[peer]:
                self.prune(peer, val, "FC", {(r, c)})
                if not self.domains[peer]:
                    return False
        return True

    def revise(self, x, y):
        # Với X != Y, giá trị x thiếu support chỉ khi D(Y) = {x}.
        if len(self.domains[y]) == 1 and self.domains[y][0] in self.domains[x]:
            causes = self.reasons[y] | ({y} if self.board[y[0]][y[1]] else set())
            self.prune(x, self.domains[y][0], "AC-3", causes)
            return True
        return False

    def ac3(self, queue):
        queue = deque(queue)
        while queue:
            self.check_budget()
            x, y = queue.popleft()
            if self.revise(x, y):
                if not self.domains[x]:
                    return False
                queue.extend((z, x) for z in sorted(self.peers[x]) if z != y)
        return True

    def backtrack(self):
        """Template Method duy nhất: chọn biến → giá trị → inference → rollback.

        Trả (solved, conflict_set). CBJ chuyển conflict_set qua những tầng
        không liên quan; Standard luôn thử hết giá trị ở tầng hiện tại.
        """
        self.check_budget()
        cell = (self.select_unassigned_variable_mrv() if self.config.use_mrv
                else self.select_unassigned_variable())
        if cell is None:
            return True, set()
        r, c = cell
        values = (self.order_domain_values_lcv(r, c) if self.config.use_lcv
                  else list(self.domains[cell]))
        conflicts = set(self.reasons[cell])
        # Bao gồm cả giá trị LCV đã lọc vì xung đột trực tiếp.
        conflicts.update(p for p in self.peers[cell]
                         if self.board[p[0]][p[1]] in self.domains[cell])
        for val in values:
            if not self.is_safe(r, c, val):
                continue
            # Backup TRƯỚC KHI đổi cả domain của ô được chọn lẫn láng giềng.
            saved_domains = deepcopy(self.domains)
            saved_reasons = deepcopy(self.reasons)
            self.assign(r, c, val, "DFS")
            self.domains[cell] = [val]
            self.reasons[cell] = {cell}
            consistent = True
            if self.config.inference == "fc":
                consistent = self.forward_check(r, c, val)
            elif self.config.inference == "ac3":
                consistent = self.ac3((p, cell) for p in sorted(self.peers[cell]))
            if consistent:
                solved, causes = self.backtrack()
                if solved:
                    return True, set()
            else:
                causes = set().union(*(self.reasons[p] for p in self.cells if not self.domains[p]))
            self.domains = saved_domains
            self.reasons = saved_reasons
            self.unassign(r, c)
            if self.config.backtrack_strategy == "cbj" and cell not in causes:
                # Việc xóa ô đã tăng backtracks; không đếm hai lần cùng rollback.
                self.record_step("BACKTRACK", log=f"CBJ: bỏ qua ({r + 1},{c + 1}), không thuộc tập xung đột {sorted(causes)}.")
                return False, causes
            conflicts.update(causes - {cell})
        return False, conflicts - self.locked_cells

    def conflict_count(self, cell, val):
        return sum(self.board[a][b] == val for a, b in self.peers[cell])

    def total_conflicts(self):
        # Mỗi cạnh vô hướng được đếm hai lần từ hai đầu mút.
        return sum(self.conflict_count(cell, self.board[cell[0]][cell[1]])
                   for cell in self.cells) // 2

    def initialize_local_search(self, mutable):
        self.check_budget()
        # Đổi toàn bộ trạng thái như một thao tác nguyên tử; chỉ ghi khi đã kín.
        for r, c in mutable:
            self.board[r][c] = self.random.randint(1, 9)
        self.assignments += len(mutable)
        self.record_step("ASSIGN", log="Min-Conflicts: khởi tạo/restart bảng đầy ngẫu nhiên.")

    def solve_local_search(self):
        mutable = [cell for cell in self.cells if cell not in self.locked_cells]
        self.initialize_local_search(mutable)
        best = self.total_conflicts()
        stagnant = 0
        for _ in range(self.max_steps):
            self.check_budget()
            conflicted = [cell for cell in mutable
                          if self.conflict_count(cell, self.board[cell[0]][cell[1]])]
            if not conflicted:
                return True
            r, c = self.random.choice(conflicted)
            before = self.total_conflicts()
            # Các cạnh không nối ô này không thay đổi: tối thiểu lỗi cục bộ
            # tương đương tối thiểu TỔNG lỗi, không cần dựng 9 bản sao board.
            scores = {v: self.conflict_count((r, c), v) for v in range(1, 10)}
            minimum = min(scores.values())
            val = self.random.choice([v for v in scores if scores[v] == minimum])
            self.check_budget()
            self.board[r][c] = val
            self.assignments += 1
            after = self.total_conflicts()
            self.record_step("ASSIGN", r, c, val,
                             f"Min-Conflicts: đổi ({r + 1},{c + 1}) thành {val}; lỗi {before} → {after}.")
            if after == 0:
                return True
            if after < best:
                best, stagnant = after, 0
            else:
                stagnant += 1
            if stagnant >= 500:
                self.initialize_local_search(mutable)
                best, stagnant = self.total_conflicts(), 0
        return self.total_conflicts() == 0

    def solve(self):
        # API tuần tự hóa lời gọi này. Không dừng tracer do caller sở hữu.
        owns_tracer = not tracemalloc.is_tracing()
        if owns_tracer:
            tracemalloc.start()
        try:
            return self._solve_recorded()
        finally:
            if owns_tracer:
                tracemalloc.stop()

    def _solve_recorded(self):
        self.started = perf_counter()
        try:
            if self.config.base_algorithm == "local_search":
                solved = self.solve_local_search()
            else:
                # AC ban đầu cần quét toàn bộ cung để duy trì invariant MAC.
                consistent = (self.ac3((x, y) for x in self.cells
                                       for y in sorted(self.peers[x]))
                              if self.config.inference == "ac3" else True)
                solved = consistent and self.backtrack()[0]
            status = "success" if solved else (
                "not_found" if self.config.base_algorithm == "local_search" else "unsolvable")
            message = {"success": "Đã tìm thấy lời giải thỏa mọi ràng buộc!",
                       "unsolvable": "Đã duyệt hết không gian tìm kiếm: đề vô nghiệm.",
                       "not_found": "Hết ngân sách Min-Conflicts; chưa tìm thấy, không kết luận vô nghiệm."}[status]
        except SearchLimit as exc:
            status, message = "limit_reached", str(exc) + " Chưa kết luận vô nghiệm."
        self.record_step("SUCCESS" if status == "success" else "FAIL", log=message)
        metrics = self.metrics()
        self.history[-1]["metrics"] = metrics
        summary = ("Local Search / Min-Conflicts" if self.config.base_algorithm == "local_search"
                   else f"DFS / {self.config.inference.value} / MRV={self.config.use_mrv} / LCV={self.config.use_lcv} / {self.config.backtrack_strategy.value}")
        return {"status": status, "config_summary": summary,
                "metrics": metrics, "history": self.history}