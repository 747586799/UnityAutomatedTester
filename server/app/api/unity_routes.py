from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.manager import UnityInstanceManager
from app.core.models import (
    ManualUnityInstanceRequest,
    PaginatedResponse,
    ReportCompareResult,
    StopUnityRequest,
    StopUnityResponse,
    UnityGroupHistoryRecord,
    UnityGroupHistorySummary,
    UnityHistoryRecord,
    UnityInstance,
    UnityInstanceGroupSummary,
    UnityLaunchGroupRequest,
)
from app.dependencies import get_history_store, get_launch_config_store, get_unity_manager
from app.protocol.messages import SendMessageRequest, SendMessageResponse
from app.runtime.history_store import HistoryStore
from app.runtime.launch_config import LaunchConfigStore
from pathlib import Path

router = APIRouter(prefix="/api/unity", tags=["unity"])


class BatchDeleteHistoryRequest(BaseModel):
    history_ids: list[str]


@router.get("/launch-config")
def get_launch_config(
    launch_config: LaunchConfigStore = Depends(get_launch_config_store),
) -> dict:
    return launch_config.load()


@router.post("/manual", response_model=UnityInstance)
def register_manual_unity(
    request: ManualUnityInstanceRequest,
    manager: UnityInstanceManager = Depends(get_unity_manager),
) -> UnityInstance:
    return manager.register_manual_instance(request.instance_id, request.project_path)


# ── Group routes ──

@router.post("/groups/start", response_model=UnityInstanceGroupSummary)
async def start_unity_group(
    request: UnityLaunchGroupRequest,
    manager: UnityInstanceManager = Depends(get_unity_manager),
    launch_config: LaunchConfigStore = Depends(get_launch_config_store),
) -> UnityInstanceGroupSummary:
    try:
        result = await manager.start_group(request)
        # 保存启动参数以便下次重启后恢复
        launch_config.save(request.model_dump(mode="json", exclude_none=True))
        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/groups", response_model=list[UnityInstanceGroupSummary])
def list_unity_groups(
    manager: UnityInstanceManager = Depends(get_unity_manager),
) -> list[UnityInstanceGroupSummary]:
    return manager.list_groups()


@router.get("/groups/{group_id}", response_model=UnityInstanceGroupSummary)
def get_unity_group(
    group_id: str,
    manager: UnityInstanceManager = Depends(get_unity_manager),
) -> UnityInstanceGroupSummary:
    group = manager.get_group(group_id)
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


# ── Group history routes ──

@router.get("/history/groups", response_model=PaginatedResponse[UnityGroupHistorySummary])
def list_group_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    history_store: HistoryStore = Depends(get_history_store),
) -> dict:
    items, total = history_store.list_group_history(page=page, page_size=page_size)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }


@router.delete("/history/groups")
def delete_group_histories(
    request: BatchDeleteHistoryRequest,
    history_store: HistoryStore = Depends(get_history_store),
) -> dict[str, list[str]]:
    return history_store.delete_group_histories(request.history_ids)


@router.get("/history/groups/{group_history_id}", response_model=UnityGroupHistoryRecord)
def get_group_history_detail(
    group_history_id: str,
    history_store: HistoryStore = Depends(get_history_store),
) -> UnityGroupHistoryRecord:
    record = history_store.get_group_history(group_history_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Group history record not found")
    return record


@router.get("/history/groups/{group_history_id}/compare-report", response_model=ReportCompareResult | None)
def get_group_report_compare(
    group_history_id: str,
    history_store: HistoryStore = Depends(get_history_store),
) -> ReportCompareResult | None:
    record = history_store.get_group_history(group_history_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Group history record not found")
    return record.report_compare


@router.get(
    "/history/groups/{group_history_id}/instances/{instance_id}",
    response_model=UnityHistoryRecord,
)
def get_group_instance_history_detail(
    group_history_id: str,
    instance_id: str,
    history_store: HistoryStore = Depends(get_history_store),
) -> UnityHistoryRecord:
    record = history_store.get_group_instance_history(group_history_id, instance_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Instance history not found in group archive")
    return record


# ── Instance operation routes (within group context) ──

@router.get("/{instance_id}", response_model=UnityInstance)
def get_unity_instance(
    instance_id: str,
    manager: UnityInstanceManager = Depends(get_unity_manager),
) -> UnityInstance:
    instance = manager.get_instance(instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Unity instance not found")
    return instance


@router.post("/{instance_id}/message", response_model=SendMessageResponse)
async def send_unity_message(
    instance_id: str,
    request: SendMessageRequest,
    manager: UnityInstanceManager = Depends(get_unity_manager),
) -> SendMessageResponse:
    message = await manager.send_message(instance_id, request)
    if message is None:
        raise HTTPException(status_code=409, detail="Unity instance is not connected")
    return SendMessageResponse(success=True, message_id=message.id)


@router.post("/{instance_id}/stop", response_model=StopUnityResponse)
async def stop_unity_instance(
    instance_id: str,
    request: StopUnityRequest | None = None,
    manager: UnityInstanceManager = Depends(get_unity_manager),
) -> StopUnityResponse:
    instance = await manager.stop_instance(instance_id, force=request.force if request else False)
    if instance is None:
        raise HTTPException(status_code=404, detail="Unity instance not found")
    return StopUnityResponse(success=True, id=instance.id, state=instance.state)


@router.get("/{instance_id}/logs")
def get_unity_logs(
    instance_id: str,
    manager: UnityInstanceManager = Depends(get_unity_manager),
) -> dict:
    instance = manager.get_instance(instance_id)
    if instance is None:
        raise HTTPException(status_code=404, detail="Unity instance not found")
    return {"id": instance.id, "logs": instance.logs}
