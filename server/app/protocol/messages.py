from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class UnityMessage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    instance_id: str
    type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    payload: dict[str, Any] = Field(default_factory=dict)


class SendMessageRequest(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)


class SendMessageResponse(BaseModel):
    success: bool
    message_id: str


class ErrorResponse(BaseModel):
    error: dict[str, Any]
