import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class LaunchConfigStore:
    """持久化启动组参数，Server 重启后可恢复最后一次的启动配置。"""

    def __init__(self, runtime_root: Path) -> None:
        self._path = Path(runtime_root) / ".launch_config.json"

    def load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self, config: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
