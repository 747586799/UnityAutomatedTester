from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.agents.models import AgentMessage
from app.agents.registry import AgentRegistry
from app.dependencies import get_agent_registry, get_unity_manager
from app.core.manager import UnityInstanceManager

import logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.websocket("/ws/agent")
async def agent_websocket(
    websocket: WebSocket,
    registry: AgentRegistry = Depends(get_agent_registry),
    manager: UnityInstanceManager = Depends(get_unity_manager),
) -> None:
    await websocket.accept()
    agent_id: str | None = None
    try:
        raw_hello = await websocket.receive_json()
        hello = AgentMessage.model_validate(raw_hello)
        if hello.type != "agent_hello":
            await websocket.close(code=1008, reason="agent_hello message is required")
            return

        agent_id = hello.agent_id
        await registry.register(agent_id, websocket, hello.payload)
        await websocket.send_json({"type": "agent_registered", "agent_id": agent_id})

        while True:
            raw_message = await websocket.receive_json()
            message = AgentMessage.model_validate(raw_message)
            if message.type == "agent_heartbeat":
                registry.heartbeat(message.agent_id, message.payload)
            elif message.type == "start_result":
                manager.on_agent_start_result(message)
            elif message.type == "process_exited":
                await manager.on_agent_process_exited(message)
            elif message.type == "sync_slots":
                registry.sync_slots(message.agent_id, message.payload.get("project_slots", []))
    except WebSocketDisconnect:
        pass
    except ValidationError as exc:
        logger.warning("Agent message validation error: %s", exc.errors())
        try:
            await websocket.send_json({"error": "invalid_agent_message", "details": exc.errors()})
        except Exception:
            pass
        try:
            await websocket.close(code=1008, reason="invalid_agent_message")
        except Exception:
            pass
    except Exception as exc:
        logger.exception("Unhandled error in agent websocket handler")
        try:
            await websocket.close(code=1011, reason="internal_server_error")
        except Exception:
            pass
    finally:
        if agent_id:
            registry.disconnect(agent_id)
