import json
from pathlib import Path
from typing import Any


class AutomationTaskTemplateStore:
    def __init__(self, runtime_root: Path) -> None:
        self._path = Path(runtime_root) / ".automation_task_template.json"

    def load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self, template: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(template, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
