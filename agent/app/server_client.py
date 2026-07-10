import asyncio
import json
import platform
import socket
from typing import Any

import websockets

from app.launcher import ProcessRegistry
from app.models import AgentConfig, AgentMessage


class AgentServerClient:
    def __init__(self, config: AgentConfig, on_connected=None) -> None:
        self.config = config
        self.processes = ProcessRegistry()
        self._running = False
        self._on_connected = on_connected
        self._websocket = None

    async def run(self) -> None:
        self._running = True
        self._loop = asyncio.get_running_loop()
        while self._running:
            try:
                async with websockets.connect(self.config.server_url) as websocket:
                    await websocket.send(self._message("agent_hello", payload=self._hello_payload()).model_dump_json())
                    heartbeat_task = asyncio.create_task(self._heartbeat_loop(websocket))
                    try:
                        async for raw in websocket:
                            await self._handle_message(websocket, json.loads(raw))
                    finally:
                        heartbeat_task.cancel()
            except Exception as exc:
                print(f"连接失败: {exc}")
                await asyncio.sleep(3)

    def stop(self) -> None:
        self._running = False

    async def _heartbeat_loop(self, websocket: Any) -> None:
        while True:
            await asyncio.sleep(5)
            await websocket.send(self._message(
                "agent_heartbeat",
                payload={"running_count": self.processes.running_count()},
            ).model_dump_json())

    async def _handle_message(self, websocket: Any, raw: dict[str, Any]) -> None:
        if "type" not in raw:
            return
        if raw.get("error"):
            print(f"服务器错误: {raw.get('error')}")
            return
        if raw["type"] == "agent_registered":
            self._websocket = websocket
            if self._on_connected:
                self._on_connected()
            return
        message = AgentMessage.model_validate(raw)
        if message.type == "start_unity" and message.instance_id:
            await self._start_unity(websocket, message)
        elif message.type == "stop_unity" and message.instance_id:
            await self._stop_unity(websocket, message)

    async def _start_unity(self, websocket: Any, message: AgentMessage) -> None:
        try:
            pid, command = await self.processes.start_unity(message.instance_id or "", message.payload, self.config)
            await websocket.send(self._message(
                "start_result",
                request_id=message.request_id,
                instance_id=message.instance_id,
                payload={"success": True, "process_id": pid, "launch_command": command},
            ).model_dump_json())
            asyncio.create_task(self._watch_process(websocket, message.instance_id or ""))
        except Exception as exc:
            await websocket.send(self._message(
                "start_result",
                request_id=message.request_id,
                instance_id=message.instance_id,
                payload={"success": False, "error": str(exc)},
            ).model_dump_json())

    async def _stop_unity(self, websocket: Any, message: AgentMessage) -> None:
        exit_code = await self.processes.stop(message.instance_id or "", bool(message.payload.get("force")))
        await websocket.send(self._message(
            "process_exited",
            request_id=message.request_id,
            instance_id=message.instance_id,
            payload={"exit_code": exit_code},
        ).model_dump_json())

    async def _watch_process(self, websocket: Any, instance_id: str) -> None:
        exit_code = await self.processes.wait_for_exit(instance_id)
        await websocket.send(self._message(
            "process_exited",
            instance_id=instance_id,
            payload={"exit_code": exit_code},
        ).model_dump_json())

    async def send_sync_slots(self, project_slots: list[dict] | None = None) -> None:
        if self._websocket is None:
            return
        slots = project_slots if project_slots is not None else [slot.model_dump(mode="json") for slot in self.config.project_slots]
        await self._websocket.send(self._message(
            "sync_slots",
            payload={"project_slots": slots},
        ).model_dump_json())

    def _hello_payload(self) -> dict[str, Any]:
        return {
            "server_id": self.config.server_id,
            "hostname": socket.gethostname(),
            "ip": self._local_ip(),
            "os": platform.system().lower(),
            "project_slots": [slot.model_dump(mode="json") for slot in self.config.project_slots],
        }

    def _message(
        self,
        message_type: str,
        request_id: str | None = None,
        instance_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AgentMessage:
        return AgentMessage(
            type=message_type,
            agent_id=self.config.agent_id,
            request_id=request_id,
            instance_id=instance_id,
            payload=payload or {},
        )

    def _local_ip(self) -> str | None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                return sock.getsockname()[0]
        except Exception:
            return None
