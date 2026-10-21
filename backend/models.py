"""Hợp đồng API: kiểm tra dữ liệu trước khi bộ giải chạy."""

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt

Digit = Annotated[StrictInt, Field(ge=0, le=9)]
Row = Annotated[list[Digit], Field(min_length=9, max_length=9)]
Board = Annotated[list[Row], Field(min_length=9, max_length=9)]


class BaseAlgorithm(str, Enum):
    BACKTRACKING = "backtracking"
    LOCAL_SEARCH = "local_search"


class InferenceType(str, Enum):
    NONE = "none"
    FC = "fc"
    AC3 = "ac3"


class BacktrackStrategy(str, Enum):
    STANDARD = "standard"
    CBJ = "cbj"


class Action(str, Enum):
    ASSIGN = "ASSIGN"
    BACKTRACK = "BACKTRACK"
    PRUNE = "PRUNE"
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"


class SolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    board: Board
    base_algorithm: BaseAlgorithm
    inference: InferenceType = InferenceType.NONE
    use_mrv: StrictBool = False
    use_lcv: StrictBool = False
    backtrack_strategy: BacktrackStrategy = BacktrackStrategy.STANDARD


class Metrics(BaseModel):
    execution_time_ms: float
    peak_memory_kb: float
    total_assignments: int
    total_backtracks: int
    total_prunes: int


class HistoryStep(BaseModel):
    step: int
    action: Action
    cell: tuple[int, int] | None
    value: int | None
    board_snapshot: Board
    log: str
    metrics: Metrics


class SolveResponse(BaseModel):
    status: Literal["success", "unsolvable", "not_found", "limit_reached"]
    config_summary: str
    metrics: Metrics
    history: list[HistoryStep]