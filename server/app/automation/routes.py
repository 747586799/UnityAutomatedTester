from fastapi import APIRouter, Depends, HTTPException

from app.automation.models import (
    AutoTask,
    AutoTaskDetailResponse,
    AutoTaskState,
    AutoTaskSummary,
    CreateAutoTaskRequest,
    UpdateAutoTaskRequest,
)
from app.automation.scheduler import AutoTaskScheduler
from app.automation.store import AutoTaskStore
from app.automation.template_store import AutomationTaskTemplateStore
from app.dependencies import get_auto_task_scheduler, get_auto_task_store, get_automation_template_store, get_history_store
from app.runtime.history_store import HistoryStore

router = APIRouter(prefix="/api/automation", tags=["automation"])


@router.get("/tasks", response_model=list[AutoTask])
def list_tasks(store: AutoTaskStore = Depends(get_auto_task_store)) -> list[AutoTask]:
    return store.list()


@router.get("/task-template")
def get_task_template(
    template_store: AutomationTaskTemplateStore = Depends(get_automation_template_store),
) -> dict:
    return template_store.load()


@router.post("/tasks", response_model=AutoTask)
def create_task(
    request: CreateAutoTaskRequest,
    store: AutoTaskStore = Depends(get_auto_task_store),
    template_store: AutomationTaskTemplateStore = Depends(get_automation_template_store),
) -> AutoTask:
    if not request.instances:
        raise HTTPException(status_code=400, detail="instances is required")
    task = store.create(request)
    template_store.save(request.model_dump(mode="json"))
    return task


@router.get("/tasks/{task_id}", response_model=AutoTaskDetailResponse)
def get_task_detail(
    task_id: str,
    store: AutoTaskStore = Depends(get_auto_task_store),
) -> AutoTaskDetailResponse:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return AutoTaskDetailResponse(task=task, summary=_build_summary(task), runs=list(reversed(task.runs)))


def _build_summary(task: AutoTask) -> AutoTaskSummary:
    total_runs = len([run for run in task.runs if run.state != "running"])
    success_runs = len([run for run in task.runs if run.state == "completed" and run.total > 0 and run.failed == 0 and run.completed == run.total])
    failed_runs = total_runs - success_runs
    checked = [run for run in task.runs if run.report_same is not None]
    report_success = len([run for run in checked if run.report_same is True])
    report_failed = len([run for run in checked if run.report_same is False])
    battle_checked = [run for run in task.runs if run.battle_match is not None]
    battle_match = len([run for run in battle_checked if run.battle_match is True])
    battle_mismatch = len([run for run in battle_checked if run.battle_match is False])
    return AutoTaskSummary(
        total_runs=total_runs,
        success_runs=success_runs,
        failed_runs=failed_runs,
        report_checked_runs=len(checked),
        report_success_runs=report_success,
        report_failed_runs=report_failed,
        run_success_rate=success_runs / total_runs if total_runs else 0.0,
        run_failed_rate=failed_runs / total_runs if total_runs else 0.0,
        report_success_rate=report_success / len(checked) if checked else 0.0,
        report_failed_rate=report_failed / len(checked) if checked else 0.0,
        battle_checked_runs=len(battle_checked),
        battle_match_runs=battle_match,
        battle_mismatch_runs=battle_mismatch,
        battle_match_rate=battle_match / len(battle_checked) if battle_checked else 0.0,
        battle_mismatch_rate=battle_mismatch / len(battle_checked) if battle_checked else 0.0,
    )


@router.put("/tasks/{task_id}", response_model=AutoTask)
def update_task(
    task_id: str,
    request: UpdateAutoTaskRequest,
    store: AutoTaskStore = Depends(get_auto_task_store),
) -> AutoTask:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if task.state == AutoTaskState.RUNNING:
        raise HTTPException(status_code=400, detail="running task cannot be updated")
    updated = store.update(task_id, request)
    if updated is None:
        raise HTTPException(status_code=404, detail="task not found")
    return updated


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: str,
    store: AutoTaskStore = Depends(get_auto_task_store),
) -> dict[str, bool]:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    if task.state == AutoTaskState.RUNNING:
        raise HTTPException(status_code=400, detail="running task cannot be deleted")
    return {"deleted": store.delete(task_id)}


@router.post("/tasks/{task_id}/start", response_model=AutoTask)
def start_task(
    task_id: str,
    store: AutoTaskStore = Depends(get_auto_task_store),
    scheduler: AutoTaskScheduler = Depends(get_auto_task_scheduler),
) -> AutoTask:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return scheduler.start_task(task)


@router.post("/tasks/{task_id}/stop", response_model=AutoTask)
def stop_task(
    task_id: str,
    store: AutoTaskStore = Depends(get_auto_task_store),
    scheduler: AutoTaskScheduler = Depends(get_auto_task_scheduler),
) -> AutoTask:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return scheduler.stop_task(task)


@router.post("/tasks/{task_id}/refresh-battle-logs")
def refresh_task_battle_logs(
    task_id: str,
    store: AutoTaskStore = Depends(get_auto_task_store),
    history_store: HistoryStore = Depends(get_history_store),
):
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")

    for run in task.runs:
        if run.state == "running" or not run.history_id or run.history_missing:
            continue
        if run.report_same is True and run.battle_match is True:
            continue
        battle_compare = history_store.refresh_group_battle_logs(run.history_id, task.battle_log_root)
        if battle_compare is not None:
            run.battle_match = battle_compare.all_match
            if run.history_summary is not None:
                run.history_summary.battle_match = battle_compare.all_match
    store.save_task(task)
    return {"success": True}
