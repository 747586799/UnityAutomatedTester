import asyncio
import logging
import time
from datetime import datetime, timedelta

from app.automation.models import AutoTask, AutoTaskRunRecord, AutoTaskState
from app.automation.store import AutoTaskStore
from app.core.manager import UnityInstanceManager
from app.core.models import UnityLaunchGroupRequest
from app.core.states import UnityInstanceState
from app.runtime.history_store import HistoryStore

logger = logging.getLogger("unity_automated_tester.automation")

TERMINAL_STATES = {
    UnityInstanceState.COMPLETED,
    UnityInstanceState.FAILED,
    UnityInstanceState.STOPPED,
    UnityInstanceState.TIMEOUT,
    UnityInstanceState.DISCONNECTED,
}


class AutoTaskScheduler:
    def __init__(
        self,
        store: AutoTaskStore,
        manager: UnityInstanceManager,
        history_store: HistoryStore,
        tick_seconds: float = 2.0,
    ) -> None:
        self._store = store
        self._manager = manager
        self._history_store = history_store
        self._tick_seconds = tick_seconds
        self._task: asyncio.Task | None = None
        self._running = False
        # Cooldown per group_id: last time we did a history lookup (avoids 2s re-scan)
        self._history_lookup_cooldown: dict[str, float] = {}

    def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self.tick()
            except Exception:
                logger.exception("Auto task scheduler tick failed")
            await asyncio.sleep(self._tick_seconds)

    async def tick(self) -> None:
        for task in self._store.list():
            if task.state == AutoTaskState.RUNNING:
                await self._check_running_task(task)
            elif task.state in {AutoTaskState.WAITING, AutoTaskState.BLOCKED}:
                await self._try_start_task(task)

    def start_task(self, task: AutoTask) -> AutoTask:
        task.state = AutoTaskState.WAITING
        task.next_run_time = datetime.now()
        task.last_error = None
        self._store.save_task(task)
        return task

    def stop_task(self, task: AutoTask) -> AutoTask:
        task.state = AutoTaskState.STOPPED
        task.next_run_time = None
        self._store.save_task(task)
        return task

    async def _try_start_task(self, task: AutoTask) -> None:
        now = datetime.now()
        if task.next_run_time and now < task.next_run_time:
            return
        if task.max_runs is not None and task.current_run_count >= task.max_runs:
            task.state = AutoTaskState.STOPPED
            task.next_run_time = None
            self._store.save_task(task)
            return

        # Set battle log root for this task
        self._history_store.set_battle_log_root(task.battle_log_root)

        request = UnityLaunchGroupRequest(
            group_name=task.group_name or task.name,
            launch_target="agent",
            project_id=task.project_id,
            execute_method=task.execute_method,
            group_args=task.group_args,
            instances=task.instances,
        )
        try:
            summary = await self._manager.start_group(request)
            task.state = AutoTaskState.RUNNING
            task.last_group_id = summary.group_id
            task.last_error = None
            task.last_run_time = now
            task.next_run_time = None
            task.runs.append(AutoTaskRunRecord(
                task_id=task.task_id,
                group_id=summary.group_id,
                group_name=summary.group_name,
                started_time=now,
                state="running",
                total=summary.total,
            ))
            self._store.save_task(task)
        except ValueError as exc:
            task.state = AutoTaskState.BLOCKED
            task.last_error = str(exc)
            self._store.save_task(task)
        except Exception as exc:
            task.state = AutoTaskState.ERROR
            task.last_error = str(exc)
            task.next_run_time = None
            self._store.save_task(task)

    async def _check_running_task(self, task: AutoTask) -> None:
        if not task.last_group_id:
            task.state = AutoTaskState.WAITING
            task.next_run_time = datetime.now()
            self._store.save_task(task)
            return

        group = self._manager.get_group(task.last_group_id)
        if group is not None and self._is_execution_timed_out(task):
            await self._stop_timed_out_group(task, group)
            return

        if group is None:
            now_ts = time.time()
            last = self._history_lookup_cooldown.get(task.last_group_id, 0)
            if now_ts - last < 15:  # don't re-scan every 2s
                return
            self._history_lookup_cooldown[task.last_group_id] = now_ts
            history_id = self._history_store.find_latest_group_history_id(task.last_group_id)
            if history_id is None:
                return
        else:
            if not group.instances:
                return
            if any(inst.state not in TERMINAL_STATES for inst in group.instances):
                return

        now = datetime.now()
        self._finalize_run_record(task, now)
        if task.last_group_id:
            self._history_lookup_cooldown.pop(task.last_group_id, None)
        task.current_run_count += 1
        if task.max_runs is not None and task.current_run_count >= task.max_runs:
            task.state = AutoTaskState.STOPPED
            task.next_run_time = None
        else:
            task.state = AutoTaskState.WAITING
            task.next_run_time = now + timedelta(seconds=max(0, task.interval_seconds))
        self._store.save_task(task)

    def _is_execution_timed_out(self, task: AutoTask) -> bool:
        if not task.execution_timeout_seconds or task.execution_timeout_seconds <= 0:
            return False
        if task.last_run_time is None:
            return False
        return datetime.now() - task.last_run_time >= timedelta(seconds=task.execution_timeout_seconds)

    async def _stop_timed_out_group(self, task: AutoTask, group) -> None:
        message = f"单次执行超过时限 {task.execution_timeout_seconds}s，已停止正在运行的实例"
        logger.warning("Auto task run timed out: task_id=%s group_id=%s timeout=%ss", task.task_id, task.last_group_id, task.execution_timeout_seconds)
        for inst in group.instances:
            if inst.state in TERMINAL_STATES:
                continue
            try:
                await self._manager.stop_instance(inst.id, force=True)
            except Exception:
                logger.warning("Failed to stop timed out instance: instance_id=%s", inst.id, exc_info=True)
        run = next((item for item in reversed(task.runs) if item.group_id == task.last_group_id), None)
        if run is not None:
            run.state = "timeout"
            run.error = message
            run.finished_time = datetime.now()
        task.last_error = message
        self._store.save_task(task)

    def _finalize_run_record(self, task: AutoTask, now: datetime) -> None:
        run = next((item for item in reversed(task.runs) if item.group_id == task.last_group_id), None)
        if run is None:
            run = AutoTaskRunRecord(task_id=task.task_id, group_id=task.last_group_id or "", started_time=now)
            task.runs.append(run)

        run.finished_time = now
        history_id = self._history_store.find_latest_group_history_id(run.group_id)
        if history_id is None:
            run.state = "completed"
            run.history_missing = True
            return

        history = self._history_store.get_group_history(history_id)
        if history is None:
            run.state = "completed"
            run.history_id = history_id
            run.history_missing = True
            return

        summary = history.summary
        run.history_id = summary.history_id
        run.history_missing = False
        run.history_summary = summary
        run.archived_time = summary.archived_time
        run.total = summary.total
        run.completed = summary.completed
        run.failed = summary.failed
        if run.state != "timeout":
            run.state = "failed" if summary.failed > 0 else "completed"
        if history.report_compare is not None:
            run.report_same = history.report_compare.same
            run.report_summary = history.report_compare.model_dump(mode="json")
        if history.battle_compare is not None:
            run.battle_match = history.battle_compare.all_match
