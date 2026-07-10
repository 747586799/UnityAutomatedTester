from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.core.models import UnityGroupHistorySummary, UnityLaunchItem


class AutoTaskState(StrEnum):
    STOPPED = "stopped"
    WAITING = "waiting"
    RUNNING = "running"
    BLOCKED = "blocked"
    ERROR = "error"


class AutoTaskRunRecord(BaseModel):
    run_id: str = Field(default_factory=lambda: f"run-{uuid4().hex[:8]}")
    task_id: str
    group_id: str
    group_name: str | None = None
    started_time: datetime = Field(default_factory=lambda: datetime.now())
    finished_time: datetime | None = None
    archived_time: datetime | None = None
    state: str = "running"
    total: int = 0
    completed: int = 0
    failed: int = 0
    history_id: str | None = None
    history_missing: bool = False
    history_summary: UnityGroupHistorySummary | None = None
    report_same: bool | None = None
    report_summary: dict[str, Any] | None = None
    battle_match: bool | None = None
    error: str | None = None


class AutoTaskSummary(BaseModel):
    total_runs: int = 0
    success_runs: int = 0
    failed_runs: int = 0
    report_checked_runs: int = 0
    report_success_runs: int = 0
    report_failed_runs: int = 0
    run_success_rate: float = 0.0
    run_failed_rate: float = 0.0
    report_success_rate: float = 0.0
    report_failed_rate: float = 0.0
    battle_checked_runs: int = 0
    battle_match_runs: int = 0
    battle_mismatch_runs: int = 0
    battle_match_rate: float = 0.0
    battle_mismatch_rate: float = 0.0


class AutoTask(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task-{uuid4().hex[:8]}")
    name: str
    state: AutoTaskState = AutoTaskState.STOPPED
    project_id: str
    execute_method: str
    group_name: str | None = None
    interval_seconds: int = 300
    max_runs: int | None = None
    current_run_count: int = 0
    battle_log_root: str | None = None
    group_args: dict[str, str | int | float | bool] = Field(default_factory=dict)
    instances: list[UnityLaunchItem] = Field(default_factory=list)
    runs: list[AutoTaskRunRecord] = Field(default_factory=list)
    last_group_id: str | None = None
    last_error: str | None = None
    last_run_time: datetime | None = None
    next_run_time: datetime | None = None
    created_time: datetime = Field(default_factory=lambda: datetime.now())
    updated_time: datetime = Field(default_factory=lambda: datetime.now())


class AutoTaskDetailResponse(BaseModel):
    task: AutoTask
    summary: AutoTaskSummary
    runs: list[AutoTaskRunRecord]


class CreateAutoTaskRequest(BaseModel):
    name: str
    project_id: str
    execute_method: str
    group_name: str | None = None
    interval_seconds: int = 300
    max_runs: int | None = None
    battle_log_root: str | None = None
    group_args: dict[str, str | int | float | bool] = Field(default_factory=dict)
    instances: list[UnityLaunchItem]


class UpdateAutoTaskRequest(BaseModel):
    name: str | None = None
    project_id: str | None = None
    execute_method: str | None = None
    group_name: str | None = None
    interval_seconds: int | None = None
    max_runs: int | None = None
    battle_log_root: str | None = None
    group_args: dict[str, str | int | float | bool] | None = None
    instances: list[UnityLaunchItem] | None = None
