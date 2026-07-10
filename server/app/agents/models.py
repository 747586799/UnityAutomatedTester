from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AgentState(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    DISCONNECTED = "disconnected"


class AgentProjectSlotState(StrEnum):
    IDLE = "idle"
    RESERVED = "reserved"
    RUNNING = "running"
    DISCONNECTED = "disconnected"


class AgentProjectSlot(BaseModel):
    slot_id: str
    project_id: str
    unity_executable_path: str
    project_path: str
    state: AgentProjectSlotState = AgentProjectSlotState.IDLE
    occupied_by: str | None = None


class AgentCapability(BaseModel):
    project_slots: list[AgentProjectSlot] = Field(default_factory=list)


class AgentInfo(BaseModel):
    agent_id: str
    server_id: str | None = None
    hostname: str = ""
    ip: str | None = None
    os: str = ""
    state: AgentState = AgentState.ONLINE
    running_count: int = 0
    capabilities: AgentCapability = Field(default_factory=AgentCapability)
    connected_time: datetime | None = None
    last_heartbeat_time: datetime | None = None


class AgentMessage(BaseModel):
    type: str
    agent_id: str
    request_id: str | None = None
    instance_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class ProjectSlotReservation(BaseModel):
    agent_id: str
    project_id: str
    slot_id: str
    unity_executable_path: str
    project_path: str
