import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel


def _default_runtime_root() -> Path:
    base = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path.cwd()
    return base / "runtime"


class Settings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 5100
    runtime_root: Path = Path("../runtime")
    default_unity_executable: str | None = None
    connection_timeout_seconds: int = 60
    execution_timeout_seconds: int = 1800
    heartbeat_timeout_seconds: int = 30
    battle_log_root: str | None = None

    @property
    def server_url(self) -> str:
        return f"ws://{self.host}:{self.port}/ws/unity"


@lru_cache
def get_settings() -> Settings:
    return Settings(
        host=os.getenv("UAT_HOST", "127.0.0.1"),
        port=int(os.getenv("UAT_PORT", "5100")),
        runtime_root=Path(os.getenv("UAT_RUNTIME_ROOT", str(_default_runtime_root()))),
        default_unity_executable=os.getenv("UAT_DEFAULT_UNITY_EXECUTABLE"),
        connection_timeout_seconds=int(os.getenv("UAT_CONNECTION_TIMEOUT_SECONDS", "60")),
        execution_timeout_seconds=int(os.getenv("UAT_EXECUTION_TIMEOUT_SECONDS", "1800")),
        heartbeat_timeout_seconds=int(os.getenv("UAT_HEARTBEAT_TIMEOUT_SECONDS", "30")),
        battle_log_root=os.getenv("UAT_BATTLE_LOG_ROOT"),
    )
