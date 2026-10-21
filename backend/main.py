"""Chạy: python -m uvicorn backend.main:app --reload"""

from pathlib import Path
from threading import Lock

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from backend.models import SolveRequest, SolveResponse
from backend.solver import SudokuCSPSolver

app = FastAPI(title="Sudoku CSP • Record & Replay")
solve_lock = Lock()  # tracemalloc là trạng thái toàn tiến trình.


@app.post("/solve", response_model=SolveResponse)
@app.post("/api/solve", response_model=SolveResponse)
def solve(request: SolveRequest):
    # Endpoint sync được FastAPI chạy trong threadpool, không chặn event loop.
    try:
        with solve_lock:
            solver = SudokuCSPSolver(request.board, request)
            return solver.solve()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


app.mount("/", StaticFiles(directory=Path(__file__).resolve().parents[1] / "frontend",
                          html=True), name="frontend")