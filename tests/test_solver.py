from copy import deepcopy
from itertools import product
import tracemalloc

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models import SolveRequest, SolveResponse
from backend.solver import SudokuCSPSolver

SAMPLE = [
    [5,3,0,0,7,0,0,0,0], [6,0,0,1,9,5,0,0,0], [0,9,8,0,0,0,0,6,0],
    [8,0,0,0,6,0,0,0,3], [4,0,0,8,0,3,0,0,1], [7,0,0,0,2,0,0,0,6],
    [0,6,0,0,0,0,2,8,0], [0,0,0,4,1,9,0,0,5], [0,0,0,0,8,0,0,7,9],
]
SOLUTION = [
    [5,3,4,6,7,8,9,1,2], [6,7,2,1,9,5,3,4,8], [1,9,8,3,4,2,5,6,7],
    [8,5,9,7,6,1,4,2,3], [4,2,6,8,5,3,7,9,1], [7,1,3,9,2,4,8,5,6],
    [9,6,1,5,3,7,2,8,4], [2,8,7,4,1,9,6,3,5], [3,4,5,2,8,6,1,7,9],
]
CONFIGS = [dict(inference=i, use_mrv=m, use_lcv=l, backtrack_strategy=b)
           for i, m, l, b in product(("none", "fc", "ac3"), (False, True),
                                    (False, True), ("standard", "cbj"))]


def make_solver(board, config=None, **kwargs):
    flags = {"base_algorithm": "backtracking", **(config or {})}
    return SudokuCSPSolver(board, SolveRequest(board=board, **flags), **kwargs)


def assert_solution(board):
    digits = set(range(1, 10))
    assert all(set(row) == digits for row in board)
    assert all({board[r][c] for r in range(9)} == digits for c in range(9))
    assert all({board[r+i][c+j] for i in range(3) for j in range(3)} == digits
               for r in (0, 3, 6) for c in (0, 3, 6))


@pytest.mark.parametrize("config", CONFIGS)
def test_sample_solution_and_history(config):
    source = deepcopy(SAMPLE)
    solver = make_solver(source, config)
    result = solver.solve()
    SolveResponse.model_validate(result)
    assert result["status"] == "success"
    assert source == SAMPLE
    assert_solution(result["history"][-1]["board_snapshot"])
    assert result["history"][-1]["action"] == "SUCCESS"
    assert len(solver.peers[(4, 4)]) == 20
    for index, step in enumerate(result["history"], 1):
        assert step["step"] == index
        for r, c in solver.locked_cells:
            assert step["board_snapshot"][r][c] == SAMPLE[r][c]
    actions = {step["action"] for step in result["history"]}
    assert ("PRUNE" not in actions) if config["inference"] == "none" else ("PRUNE" in actions)
    assert result["metrics"]["total_assignments"] == sum(s["action"] == "ASSIGN" for s in solver.history)
    assert result["metrics"]["total_backtracks"] == sum(s["action"] == "BACKTRACK" and s["cell"] is not None for s in solver.history)
    assert result["metrics"]["total_prunes"] == sum(s["action"] == "PRUNE" for s in solver.history)
    assert result["metrics"]["peak_memory_kb"] > 0
    assert result["metrics"] == result["history"][-1]["metrics"]


@pytest.mark.parametrize("config", CONFIGS + [{"base_algorithm": "local_search"}])
def test_already_solved(config):
    result = make_solver(SOLUTION, config, seed=0).solve()
    assert result["status"] == "success"
    assert result["history"][-1]["board_snapshot"] == SOLUTION


def test_snapshot_is_deep_copy():
    solver = SudokuCSPSolver(SAMPLE)
    solver.record_step("ASSIGN", 0, 2, 4)
    solver.board[0][2] = 9
    assert solver.history[0]["board_snapshot"][0][2] == 0


@pytest.mark.parametrize("config", CONFIGS)
def test_unsolvable_without_duplicate_givens(config):
    board = deepcopy(SAMPLE)
    board[0][2] = 1  # Không trùng trực tiếp nhưng loại bỏ nghiệm duy nhất.
    result = make_solver(board, config).solve()
    assert result["status"] == "unsolvable"
    assert result["history"][-1]["action"] == "FAIL"


@pytest.mark.parametrize("config", [c for c in CONFIGS if c["inference"] != "ac3"])
def test_domains_restored_after_exhaustive_failure(config):
    board = deepcopy(SAMPLE)
    board[0][2] = 1
    solver = make_solver(board, config)
    saved = deepcopy(solver.domains)
    assert solver.solve()["status"] == "unsolvable"
    assert solver.domains == saved
    assert solver.board == board


def test_mac_restores_domains_on_failed_branch():
    solver = make_solver(SAMPLE, {"inference": "ac3"})
    # Khởi tạo AC toàn cục trước, rồi dùng DFS với MAC trên nhánh sai.
    assert solver.ac3((x, y) for x in solver.cells for y in solver.peers[x])
    solver.domains[(0, 2)] = [1]
    saved = deepcopy(solver.domains)
    assert solver.backtrack()[0] is False
    assert solver.domains == saved
    assert solver.board == SAMPLE


def test_mrv_and_lcv_explicit_ordering():
    solver = SudokuCSPSolver([[0]*9 for _ in range(9)])
    solver.domains[(4, 4)] = [2]
    assert solver.select_unassigned_variable_mrv() == (4, 4)
    solver.domains[(4, 4)] = [1, 2]
    for p in solver.peers[(4, 4)]:
        solver.domains[p] = [1, 3]
    assert solver.order_domain_values_lcv(4, 4) == [2, 1]


def test_ac3_propagates_beyond_first_neighbor():
    solver = SudokuCSPSolver([[0]*9 for _ in range(9)])
    solver.domains[(0, 0)] = [1]
    solver.domains[(0, 1)] = [1, 2]
    solver.domains[(1, 1)] = [2, 3]
    assert solver.ac3([((0, 1), (0, 0))])
    assert solver.domains[(0, 1)] == [2]
    assert solver.domains[(1, 1)] == [3]


def test_fc_detects_empty_domain():
    solver = SudokuCSPSolver([[0]*9 for _ in range(9)])
    solver.domains[(0, 1)] = [1]
    solver.board[0][0] = 1
    assert solver.forward_check(0, 0, 1) is False


def test_min_conflicts_full_snapshots_and_no_dfs_actions():
    board = deepcopy(SOLUTION)
    board[0][0] = 0
    solver = make_solver(board, {"base_algorithm": "local_search"}, seed=7)
    result = solver.solve()
    assert result["status"] == "success"
    assert_solution(result["history"][-1]["board_snapshot"])
    for step in solver.history:
        assert step["action"] not in ("BACKTRACK", "PRUNE")
        assert all(all(row) for row in step["board_snapshot"])
        for r, c in solver.locked_cells:
            assert step["board_snapshot"][r][c] == board[r][c]
    assert solver.backtracks == 0


def test_min_conflicts_budget_is_not_unsolvable():
    result = make_solver(SAMPLE, {"base_algorithm": "local_search"}, seed=0, max_steps=0).solve()
    assert result["status"] == "not_found"
    assert result["history"][-1]["action"] == "FAIL"


def test_random_restart_keeps_global_budget():
    solver = make_solver(SAMPLE, {"base_algorithm": "local_search"}, seed=0, max_steps=501)
    # Cố định điểm lỗi để buộc plateau 500 bước, không phụ thuộc may rủi.
    solver.total_conflicts = lambda: 10
    solver.conflict_count = lambda cell, val: 1
    result = solver.solve()
    assert result["status"] == "not_found"
    assert sum(s["cell"] is None and s["action"] == "ASSIGN" for s in solver.history) == 2
    assert len(solver.history) == 504  # 501 sửa + 2 khởi tạo + 1 FAIL


@pytest.mark.parametrize("kwargs", [{"max_history": 2}, {"timeout_seconds": 0}])
def test_resource_limits_have_terminal_event(kwargs):
    result = SudokuCSPSolver(SAMPLE, **kwargs).solve()
    assert result["status"] == "limit_reached"
    assert result["history"][-1]["action"] == "FAIL"


client = TestClient(app)


@pytest.mark.parametrize("url", ["/solve", "/api/solve"])
@pytest.mark.parametrize("config", CONFIGS + [{"base_algorithm": "local_search"}])
def test_api_contract(config, url):
    response = client.post(url, json={"board": SOLUTION, "base_algorithm": "backtracking", **config})
    assert response.status_code == 200
    parsed = SolveResponse.model_validate(response.json())
    assert parsed.config_summary
    assert set(response.json()["metrics"]) == {"execution_time_ms", "peak_memory_kb", "total_assignments", "total_backtracks", "total_prunes"}


@pytest.mark.parametrize("bad", [[], [[0]*9]*8, [[0]*8]*9, [[10]*9]*9,
                                 [[True]*9]*9, [["1"]*9]*9, [[1.5]*9]*9])
def test_api_invalid_board(bad):
    assert client.post("/solve", json={"board": bad, "base_algorithm": "backtracking"}).status_code == 422


def test_api_duplicate_and_unknown_algorithm():
    board = deepcopy(SAMPLE)
    board[0][2] = 5
    assert client.post("/solve", json={"board": board, "base_algorithm": "backtracking"}).status_code == 422
    assert client.post("/solve", json={"board": SAMPLE, "base_algorithm": "unknown"}).status_code == 422


@pytest.mark.parametrize("url", ["/", "/styles.css", "/app.js", "/replay.js", "/docs"])
def test_frontend_served(url):
    assert client.get(url).status_code == 200