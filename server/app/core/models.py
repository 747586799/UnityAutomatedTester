from datetime import datetime
from pathlib import Path
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.states import UnityInstanceState

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0


class UnityLaunchOptions(BaseModel):
    unity_executable_path: str | None = None
    project_path: str
    execute_method: str = "UnityAutomatedTester.EntryPoint.Run"
    args: dict[str, str | int | float | bool] = Field(default_factory=dict)


class StopUnityRequest(BaseModel):
    force: bool = False


class ManualUnityInstanceRequest(BaseModel):
    instance_id: str
    project_path: str = "manual-unity-editor"


class UnityInstance(BaseModel):
    id: str
    project_path: str
    unity_executable_path: str | None = None
    execute_method: str
    launch_target: str = "local"
    agent_id: str | None = None
    project_id: str | None = None
    project_slot_id: str | None = None
    request_id: str | None = None
    process_id: int | None = None
    state: UnityInstanceState = UnityInstanceState.CREATED
    start_time: datetime = Field(default_factory=lambda: datetime.now())
    connected_time: datetime | None = None
    end_time: datetime | None = None
    last_heartbeat_time: datetime | None = None
    progress: float = 0.0
    log_file: Path | None = None
    result_file: Path | None = None
    exit_code: int | None = None
    error_message: str | None = None
    args: dict[str, str | int | float | bool] = Field(default_factory=dict)
    launch_command: list[str] = Field(default_factory=list)
    logs: list[dict[str, Any]] = Field(default_factory=list)
    result: dict[str, Any] | None = None
    group_id: str | None = None
    group_name: str | None = None
    launch_name: str | None = None
    ready_id: int | None = None
    ready_time: datetime | None = None
    start_signal_sent: bool = False


class UnityInstanceSummary(BaseModel):
    id: str
    state: UnityInstanceState
    process_id: int | None = None
    progress: float = 0.0
    group_id: str | None = None
    group_name: str | None = None
    launch_name: str | None = None
    launch_target: str = "local"
    agent_id: str | None = None
    project_id: str | None = None
    project_slot_id: str | None = None
    ready_id: int | None = None
    start_signal_sent: bool = False


class StopUnityResponse(BaseModel):
    success: bool
    id: str
    state: UnityInstanceState


class UnityHistorySummary(BaseModel):
    id: str
    original_id: str
    state: str
    project_path: str
    execute_method: str
    process_id: int | None = None
    progress: float = 0.0
    start_time: str = ""
    end_time: str | None = None
    archived_time: str = ""
    error_message: str | None = None


class UnityHistoryRecord(BaseModel):
    summary: UnityHistorySummary
    result: dict[str, Any] | None = None
    report: str | None = None
    error_message: str | None = None
    logs: list[dict[str, Any]] = Field(default_factory=list)
    launch_command: list[str] = Field(default_factory=list)
    args: dict[str, Any] = Field(default_factory=dict)
    unity_executable_path: str | None = None
    group_id: str | None = None
    group_name: str | None = None
    launch_name: str | None = None


class UnityLaunchItem(BaseModel):
    name: str | None = None
    project_path: str | None = None
    args: dict[str, str | int | float | bool] = Field(default_factory=dict)


class UnityLaunchGroupRequest(BaseModel):
    group_name: str | None = None
    launch_target: str = "agent"
    project_id: str | None = None
    unity_executable_path: str | None = None
    project_path: str | None = None
    execute_method: str
    instances: list[UnityLaunchItem]
    group_args: dict[str, str | int | float | bool] = Field(default_factory=dict)


class UnityInstanceGroupSummary(BaseModel):
    group_id: str
    group_name: str | None = None
    total: int = 0
    active: int = 0
    completed: int = 0
    failed: int = 0
    state: str = "running"
    instances: list[UnityInstanceSummary] = Field(default_factory=list)


class ReportCompareItem(BaseModel):
    instance_id: str
    launch_name: str | None = None
    sha256: str
    same_as_baseline: bool
    report_length: int


class ReportCompareResult(BaseModel):
    baseline_instance_id: str | None = None
    same: bool
    items: list[ReportCompareItem] = Field(default_factory=list)


class BattleCompareItem(BaseModel):
    instance_id: str
    launch_name: str | None = None
    report_sha256: str
    battle_sha256: str | None = None
    match: bool
    report_length: int
    battle_length: int


class BattleCompareResult(BaseModel):
    all_match: bool
    battle_room_id: str | None = None
    battle_log_missing: bool = False
    items: list[BattleCompareItem] = Field(default_factory=list)


class UnityGroupHistorySummary(BaseModel):
    history_id: str = ""
    group_id: str
    group_name: str | None = None
    total: int = 0
    completed: int = 0
    failed: int = 0
    state: str = ""
    archived_time: str = ""
    report_same: bool | None = None
    battle_match: bool | None = None


class UnityGroupHistoryRecord(BaseModel):
    summary: UnityGroupHistorySummary
    instances: list[UnityHistorySummary] = Field(default_factory=list)
    report_compare: ReportCompareResult | None = None
    battle_compare: BattleCompareResult | None = None
    instance_reports: dict[str, str] = Field(default_factory=dict)
