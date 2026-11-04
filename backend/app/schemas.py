from pydantic import BaseModel, Field
from typing import Any, Literal

class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)

class AgentStep(BaseModel):
    name: str
    status: Literal["complete", "rejected", "skipped"]
    detail: str

class AskResponse(BaseModel):
    question: str
    answer: str
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    chart: dict[str, Any] | None = None
    steps: list[AgentStep]
    duration_ms: float
    mode: str = "deterministic-demo"
