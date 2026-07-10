import json
import threading
import time
from datetime import datetime
from pathlib import Path

from app.automation.models import AutoTask, AutoTaskState, CreateAutoTaskRequest, UpdateAutoTaskRequest


class AutoTaskStore:
    _SAVE_DEBOUNCE_S = 1.0

    def __init__(self, runtime_root: Path) -> None:
        self._path = Path(runtime_root) / "automation_tasks.json"
        self._tasks: dict[str, AutoTask] = {}
        self._dirty = False
        self._last_save = 0.0
        self._save_lock = threading.Lock()
        self.load()

    def _mark_dirty(self) -> None:
        self._dirty = True

    def _flush_if_needed(self) -> None:
        with self._save_lock:
            if not self._dirty:
                return
        self._do_save()

    def _do_save(self) -> None:
        now = time.time()
        with self._save_lock:
            if not self._dirty:
                return
            if now - self._last_save < self._SAVE_DEBOUNCE_S:
                return
            self._dirty = False
            self._last_save = now
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"tasks": [task.model_dump(mode="json") for task in self._tasks.values()]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load(self) -> None:
        if not self._path.exists():
            self._tasks = {}
            return
        data = json.loads(self._path.read_text(encoding="utf-8"))
        tasks = [AutoTask.model_validate(item) for item in data.get("tasks", [])]
        # Server 閲嶅惎鍚庝笉鑷姩鎭㈠杩愯
        for task in tasks:
            task.state = AutoTaskState.STOPPED
            task.next_run_time = None
            task.last_group_id = None
            task.updated_time = datetime.now()
        self._tasks = {task.task_id: task for task in tasks}
        self.save()

    def save(self) -> None:
        self._mark_dirty()
        self._do_save()

    def list(self) -> list[AutoTask]:
        return sorted(self._tasks.values(), key=lambda task: task.created_time, reverse=True)

    def get(self, task_id: str) -> AutoTask | None:
        return self._tasks.get(task_id)

    def create(self, request: CreateAutoTaskRequest) -> AutoTask:
        task = AutoTask(**request.model_dump())
        self._tasks[task.task_id] = task
        self._mark_dirty()
        self._do_save()
        return task

    def update(self, task_id: str, request: UpdateAutoTaskRequest) -> AutoTask | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        data = request.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(task, key, value)
        task.updated_time = datetime.now()
        self._mark_dirty()
        self._do_save()
        return task

    def delete(self, task_id: str) -> bool:
        if task_id not in self._tasks:
            return False
        del self._tasks[task_id]
        self._mark_dirty()
        self._do_save()
        return True

    def set_state(self, task: AutoTask, state: AutoTaskState, error: str | None = None) -> None:
        task.state = state
        task.last_error = error
        task.updated_time = datetime.now()
        self._mark_dirty()
        self._do_save()

    def save_task(self, task: AutoTask) -> None:
        task.updated_time = datetime.now()
        self._tasks[task.task_id] = task
        self._mark_dirty()
        self._do_save()  # debounced
