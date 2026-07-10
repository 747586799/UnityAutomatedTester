from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from app.core.manager import UnityInstanceManager
from app.dependencies import get_unity_manager
from app.protocol.messages import UnityMessage
from app.protocol.types import UnityToServerMessageType

router = APIRouter()


MAX_MESSAGE_SIZE = 10 * 1024 * 1024  # 10 MB


@router.websocket("/ws/unity")
async def unity_websocket(
    websocket: WebSocket,
    manager: UnityInstanceManager = Depends(get_unity_manager),
) -> None:
    await websocket.accept()
    if hasattr(websocket, "_conn"):
        websocket._conn.max_size = MAX_MESSAGE_SIZE

    instance_id: str | None = None

    try:
        raw_hello = await websocket.receive_json()
        hello = UnityMessage.model_validate(raw_hello)
        if hello.type != UnityToServerMessageType.HELLO:
            await websocket.close(code=1008, reason="hello message is required")
            return

        instance_id = hello.instance_id
        connected = await manager.on_unity_connected(instance_id, websocket)
        if not connected:
            await websocket.close(code=1008, reason="unknown instance_id")
            return

        await manager.on_unity_message(hello)

        while True:
            raw_message = await websocket.receive_json()
            message = UnityMessage.model_validate(raw_message)
            handled = await manager.on_unity_message(message)
            if not handled:
                await websocket.send_json({"error": "unknown instance_id"})
    except WebSocketDisconnect:
        pass
    except ValidationError as exc:
        if websocket.client_state.name == "CONNECTED":
            await websocket.send_json({"error": "invalid_message", "details": exc.errors()})
    finally:
        if instance_id:
            manager.on_unity_disconnected(instance_id)
