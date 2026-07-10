from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ProjectSlotConfig(BaseModel):
    slot_id: str
    project_id: str
    unity_executable_path: str
    project_path: str
    state: str = "idle"


class AgentConfig(BaseModel):
    agent_id: str = ""
    server_id: str = "default"
    server_url: str = "ws://127.0.0.1:5100/ws/agent"
    unity_server_url: str = "ws://127.0.0.1:5100/ws/unity"
    project_slots: list[ProjectSlotConfig] = Field(default_factory=list)


class AgentMessage(BaseModel):
    type: str
    agent_id: str
    request_id: str | None = None
    instance_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
