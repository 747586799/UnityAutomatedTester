import asyncio
import logging
import re
from datetime import datetime
from uuid import uuid4

from fastapi import WebSocket

from app.agents.dispatcher import make_agent_command
from app.agents.models import AgentMessage
from app.agents.registry import AgentRegistry
from app.core.dispatcher import UnityMessageDispatcher
from app.core.launcher import UnityProcessLauncher
from app.core.models import (
    UnityInstance,
    UnityInstanceGroupSummary,
    UnityInstanceSummary,
    UnityLaunchGroupRequest,
    UnityLaunchItem,
    UnityLaunchOptions,
)
from app.core.registry import UnityConnectionRegistry
from app.core.states import UnityInstanceState
from app.protocol.messages import SendMessageRequest, UnityMessage
from app.protocol.types import ServerToUnityMessageType, UnityToServerMessageType
from app.runtime.history_store import HistoryStore
from app.runtime.workspace import RuntimeWorkspace

logger = logging.getLogger("unity_automated_tester")

TERMINAL_STATES = frozenset({
    UnityInstanceState.COMPLETED,
    UnityInstanceState.FAILED,
    UnityInstanceState.STOPPED,
    UnityInstanceState.TIMEOUT,
    UnityInstanceState.DISCONNECTED,
})


class UnityInstanceGroup:
    def __init__(self, group_id: str, group_name: str | None) -> None:
        self.id = group_id
        self.name = group_name
        self.instance_ids: list[str] = []

    @property
    def state(self) -> str:
        return "running"

    def to_summary(self, instances: dict[str, UnityInstance]) -> UnityInstanceGroupSummary:
        group_instances: list[UnityInstanceSummary] = []
        total = len(self.instance_ids)
        active = 0
        completed = 0
        failed = 0

        for inst_id in self.instance_ids:
            inst = instances.get(inst_id)
            if inst is None:
                continue
            summary = UnityInstanceSummary(
                id=inst.id,
                state=inst.state,
                process_id=inst.process_id,
                progress=inst.progress,
                group_id=self.id,
                group_name=self.name,
                launch_name=inst.launch_name,
                launch_target=inst.launch_target,
                agent_id=inst.agent_id,
                project_id=inst.project_id,
                project_slot_id=inst.project_slot_id,
                ready_id=inst.ready_id,
                start_signal_sent=inst.start_signal_sent,
            )
            group_instances.append(summary)
            if inst.state in TERMINAL_STATES:
                if inst.state == UnityInstanceState.COMPLETED:
                    completed += 1
                else:
                    failed += 1
            else:
                active += 1

        group_state = "running" if active > 0 else ("completed" if failed == 0 else "failed")

        return UnityInstanceGroupSummary(
            group_id=self.id,
            group_name=self.name,
            total=total,
            active=active,
            completed=completed,
            failed=failed,
            state=group_state,
            instances=group_instances,
        )


class UnityInstanceManager:
    def __init__(
        self,
        launcher: UnityProcessLauncher,
        registry: UnityConnectionRegistry,
        dispatcher: UnityMessageDispatcher,
        workspace: RuntimeWorkspace,
        history_store: HistoryStore | None = None,
        default_unity_executable: str | None = None,
        agent_registry: AgentRegistry | None = None,
    ) -> None:
        self._launcher = launcher
        self._registry = registry
        self._dispatcher = dispatcher
        self._workspace = workspace
        self._history_store = history_store or HistoryStore(workspace.runtime_root)
        self._default_unity_executable = default_unity_executable
        self._agent_registry = agent_registry
        self._instances: dict[str, UnityInstance] = {}
        self._groups: dict[str, UnityInstanceGroup] = {}

    def register_manual_instance(self, instance_id: str, project_path: str = "manual-unity-editor") -> UnityInstance:
        instance = UnityInstance(
            id=instance_id,
            project_path=project_path,
            execute_method="manual-editor-connection",
            state=UnityInstanceState.WAITING_FOR_CONNECTION,
            log_file=self._workspace.unity_log_path(instance_id),
            result_file=self._workspace.result_path(instance_id),
        )
        self._instances[instance_id] = instance
        return instance

    async def start_instance(self, options: UnityLaunchOptions) -> UnityInstance:
        instance_id = self._new_instance_id()
        unity_executable = options.unity_executable_path or self._default_unity_executable
        instance = UnityInstance(
            id=instance_id,
            project_path=options.project_path,
            unity_executable_path=unity_executable,
            execute_method=options.execute_method,
            state=UnityInstanceState.STARTING,
            log_file=self._workspace.unity_log_path(instance_id),
            result_file=self._workspace.result_path(instance_id),
            args=options.args,
        )
        self._instances[instance_id] = instance
        if not unity_executable:
            instance.state = UnityInstanceState.FAILED
            instance.error_message = "unity_executable is required"
            instance.end_time = datetime.now()
            return instance
        try:
            instance.launch_command = self._launcher.build_command(instance_id, options, unity_executable, instance.log_file)
            instance.process_id = await self._launcher.start(instance_id, options, unity_executable, instance.log_file)
            instance.state = UnityInstanceState.WAITING_FOR_CONNECTION
        except Exception as exc:
            instance.state = UnityInstanceState.FAILED
            instance.error_message = str(exc)
            instance.end_time = datetime.now()
        return instance

    async def start_group(self, request: UnityLaunchGroupRequest) -> UnityInstanceGroupSummary:
        if request.launch_target == "agent":
            return await self._start_agent_group(request)
        return await self._start_local_group(request)

    async def _start_local_group(self, request: UnityLaunchGroupRequest) -> UnityInstanceGroupSummary:
        group_id = self._new_group_id()
        group = UnityInstanceGroup(group_id, request.group_name)
        unity_executable = request.unity_executable_path or self._default_unity_executable

        if not unity_executable:
            raise ValueError("unity_executable is required")

        group_instances: list[UnityInstance] = []

        for item in request.instances:
            instance_id = self._new_instance_id()
            log_file = self._workspace.group_unity_log_path(group_id, instance_id)
            result_file = self._workspace.group_result_path(group_id, instance_id)
            project_path = item.project_path or request.project_path
            if not project_path:
                raise ValueError("project_path is required for each instance")

            instance_args = dict(request.group_args or {})
            instance_args.update(self._sanitize_custom_args(item.args))

            instance = UnityInstance(
                id=instance_id,
                project_path=project_path,
                unity_executable_path=unity_executable,
                execute_method=request.execute_method,
                launch_target="local",
                state=UnityInstanceState.STARTING,
                log_file=log_file,
                result_file=result_file,
                args=instance_args,
                group_id=group_id,
                group_name=request.group_name,
                launch_name=item.name,
            )
            self._instances[instance_id] = instance
            group.instance_ids.append(instance_id)
            group_instances.append(instance)

        self._groups[group_id] = group

        async def _launch_single(inst: UnityInstance) -> None:
            try:
                options = UnityLaunchOptions(
                    unity_executable_path=request.unity_executable_path,
                    project_path=inst.project_path,
                    execute_method=request.execute_method,
                    args=inst.args,
                )
                inst.launch_command = self._launcher.build_command(inst.id, options, unity_executable, inst.log_file)
                process_id = await self._launcher.start(inst.id, options, unity_executable, inst.log_file)
                inst.process_id = process_id
                inst.state = UnityInstanceState.WAITING_FOR_CONNECTION
                logger.info("Group instance launched: instance_id=%s group_id=%s", inst.id, group_id)
            except Exception as exc:
                inst.state = UnityInstanceState.FAILED
                inst.error_message = str(exc)
                inst.end_time = datetime.now()
                logger.error("Failed to launch group instance: instance_id=%s error=%s", inst.id, exc)

        await asyncio.gather(*[_launch_single(inst) for inst in group_instances])
        return group.to_summary(self._instances)

    async def _start_agent_group(self, request: UnityLaunchGroupRequest) -> UnityInstanceGroupSummary:
        if self._agent_registry is None:
            raise ValueError("agent registry is not configured")
        if not request.project_id:
            raise ValueError("project_id is required")

        reservations = self._agent_registry.reserve_slots(request.project_id, len(request.instances))
        group_id = self._new_group_id()
        group = UnityInstanceGroup(group_id, request.group_name)
        group_instances: list[UnityInstance] = []

        try:
            for item, reservation in zip(request.instances, reservations, strict=True):
                instance_id = self._new_instance_id()
                self._agent_registry.mark_slot_reserved(reservation.agent_id, reservation.slot_id, instance_id)
                log_file = self._workspace.group_unity_log_path(group_id, instance_id)
                result_file = self._workspace.group_result_path(group_id, instance_id)
                instance_args = dict(request.group_args or {})
                instance_args.update(self._sanitize_custom_args(item.args))
                request_id = f"req-{uuid4().hex[:8]}"

                instance = UnityInstance(
                    id=instance_id,
                    project_path=reservation.project_path,
                    unity_executable_path=reservation.unity_executable_path,
                    execute_method=request.execute_method,
                    launch_target="agent",
                    agent_id=reservation.agent_id,
                    project_id=reservation.project_id,
                    project_slot_id=reservation.slot_id,
                    request_id=request_id,
                    state=UnityInstanceState.STARTING,
                    log_file=log_file,
                    result_file=result_file,
                    args=instance_args,
                    group_id=group_id,
                    group_name=request.group_name,
                    launch_name=item.name,
                )
                self._instances[instance_id] = instance
                group.instance_ids.append(instance_id)
                group_instances.append(instance)

            self._groups[group_id] = group
            await asyncio.gather(*[self._start_agent_instance(inst) for inst in group_instances])
            return group.to_summary(self._instances)
        except Exception:
            for inst in group_instances:
                self._agent_registry.release_slot(inst.agent_id, inst.project_slot_id, inst.id)
                self._instances.pop(inst.id, None)
            self._groups.pop(group_id, None)
            raise

    async def _start_agent_instance(self, inst: UnityInstance) -> None:
        if self._agent_registry is None or not inst.agent_id:
            inst.state = UnityInstanceState.FAILED
            inst.error_message = "agent registry is not configured"
            inst.end_time = datetime.now()
            return

        websocket = self._agent_registry.get_connection(inst.agent_id)
        if websocket is None:
            inst.state = UnityInstanceState.FAILED
            inst.error_message = "agent is not connected"
            inst.end_time = datetime.now()
            self._release_agent_slot(inst)
            return

        payload = {
            "project_id": inst.project_id,
            "slot_id": inst.project_slot_id,
            "unity_executable_path": inst.unity_executable_path,
            "project_path": inst.project_path,
            "execute_method": inst.execute_method,
            "args": inst.args,
            "log_file": str(inst.log_file) if inst.log_file else None,
        }
        command = make_agent_command(
            "start_unity",
            agent_id=inst.agent_id,
            instance_id=inst.id,
            request_id=inst.request_id,
            payload=payload,
        )
        inst.launch_command = ["agent", inst.agent_id, "start_unity", inst.project_slot_id or ""]
        await websocket.send_json(command.model_dump(mode="json"))

    async def on_unity_ready(self, instance_id: str, ready_id: int) -> UnityInstanceGroupSummary | None:
        """Mark an instance as ready. If all instances in the group are ready, broadcast start."""
        instance = self._instances.get(instance_id)
        if instance is None:
            return None

        # Must belong to a group
        if not instance.group_id:
            return None

        group = self._groups.get(instance.group_id)
        if group is None:
            return None

        # Mark ready
        instance.ready_id = ready_id
        instance.ready_time = datetime.now()
        instance.state = UnityInstanceState.READY
        logger.info("Instance ready: instance_id=%s ready_id=%s group_id=%s", instance_id, ready_id, instance.group_id)

        # Check if all instances in the group are ready
        all_ready = True
        for inst_id in group.instance_ids:
            inst = self._instances.get(inst_id)
            if inst is None or inst.ready_id is None:
                all_ready = False
                break

        if all_ready:
            logger.info("All instances ready in group_id=%s, broadcasting start...", group.id)
            await self._broadcast_start_to_group(group.id)

        return group.to_summary(self._instances)

    async def _broadcast_start_to_group(self, group_id: str) -> None:
        """Send 'start' message to every instance in the group."""
        group = self._groups.get(group_id)
        if group is None:
            logger.warning("Group not found for broadcast start: group_id=%s", group_id)
            return

        for inst_id in group.instance_ids:
            inst = self._instances.get(inst_id)
            if inst is None:
                continue
            if inst.start_signal_sent:
                continue

            websocket = self._registry.get(inst_id)
            if websocket is None:
                logger.warning("Cannot send start - instance not connected: instance_id=%s", inst_id)
                continue

            try:
                start_msg = UnityMessage(
                    instance_id=inst_id,
                    type=ServerToUnityMessageType.START,
                    payload={
                        "id": inst.ready_id,
                        "instance_id": inst_id,
                        "group_id": group_id,
                        "args": inst.args,
                    },
                )
                await websocket.send_json(start_msg.model_dump(mode="json"))
                inst.start_signal_sent = True
                inst.state = UnityInstanceState.RUNNING
                logger.info("Start broadcast to instance: instance_id=%s ready_id=%s", inst_id, inst.ready_id)
            except Exception:
                logger.warning("Failed to send start to instance: instance_id=%s", inst_id, exc_info=True)

    async def stop_instance(self, instance_id: str, force: bool = False) -> UnityInstance | None:
        instance = self._instances.get(instance_id)
        if instance is None:
            return None

        already_terminal = instance.state in {
            UnityInstanceState.COMPLETED,
            UnityInstanceState.FAILED,
        }

        if not already_terminal:
            instance.state = UnityInstanceState.STOPPING

        if instance.launch_target == "agent":
            await self._stop_agent_instance(instance, force)
            exit_code = instance.exit_code
        else:
            exit_code = await self._launcher.stop(instance_id, force)

        instance.exit_code = exit_code

        if not already_terminal:
            instance.state = UnityInstanceState.STOPPED
            instance.end_time = datetime.now()

        self._registry.unregister(instance_id)
        self._release_agent_slot(instance)
        self._archive_if_terminal(instance)
        return instance

    async def _stop_agent_instance(self, instance: UnityInstance, force: bool) -> None:
        if self._agent_registry is None or not instance.agent_id:
            return
        websocket = self._agent_registry.get_connection(instance.agent_id)
        if websocket is None:
            return
        command = make_agent_command(
            "stop_unity",
            agent_id=instance.agent_id,
            instance_id=instance.id,
            request_id=f"req-{uuid4().hex[:8]}",
            payload={"force": force, "slot_id": instance.project_slot_id},
        )
        await websocket.send_json(command.model_dump(mode="json"))

    def list_instances(self) -> list[UnityInstanceSummary]:
        return [
            UnityInstanceSummary(
                id=instance.id,
                state=instance.state,
                process_id=instance.process_id,
                progress=instance.progress,
                group_id=instance.group_id,
                group_name=instance.group_name,
                launch_name=instance.launch_name,
                launch_target=instance.launch_target,
                agent_id=instance.agent_id,
                project_id=instance.project_id,
                project_slot_id=instance.project_slot_id,
                ready_id=instance.ready_id,
                start_signal_sent=instance.start_signal_sent,
            )
            for instance in self._instances.values()
        ]

    def get_instance(self, instance_id: str) -> UnityInstance | None:
        return self._instances.get(instance_id)

    def list_groups(self) -> list[UnityInstanceGroupSummary]:
        groups: dict[str, UnityInstanceGroupSummary] = {}
        # collect groups from active group objects
        for group in self._groups.values():
            groups[group.id] = group.to_summary(self._instances)
        # also group orphan instances by group_id
        for inst in self._instances.values():
            if inst.group_id and inst.group_id not in groups:
                g = UnityInstanceGroup(inst.group_id, inst.group_name)
                g.instance_ids.append(inst.id)
                self._groups[inst.group_id] = g
                groups[inst.group_id] = g.to_summary(self._instances)
        return list(groups.values())

    def get_group(self, group_id: str) -> UnityInstanceGroupSummary | None:
        group = self._groups.get(group_id)
        if group is None:
            # try to build from instance group_ids
            instances_in_group = [i for i in self._instances.values() if i.group_id == group_id]
            if instances_in_group:
                g = UnityInstanceGroup(group_id, instances_in_group[0].group_name)
                for inst in instances_in_group:
                    g.instance_ids.append(inst.id)
                self._groups[group_id] = g
                return g.to_summary(self._instances)
            return None
        return group.to_summary(self._instances)

    async def send_message(self, instance_id: str, request: SendMessageRequest) -> UnityMessage | None:
        websocket = self._registry.get(instance_id)
        if websocket is None:
            return None

        message = UnityMessage(
            instance_id=instance_id,
            type=request.type,
            payload=request.payload,
        )
        await websocket.send_json(message.model_dump(mode="json"))
        return message

    async def on_unity_connected(self, instance_id: str, websocket: WebSocket) -> bool:
        instance = self._instances.get(instance_id)
        if instance is None:
            return False

        self._registry.register(instance_id, websocket)
        instance.state = UnityInstanceState.CONNECTED
        instance.connected_time = datetime.now()
        instance.last_heartbeat_time = instance.connected_time
        logger.info("Unity connected: instance_id=%s", instance_id)
        return True

    async def on_unity_message(self, message: UnityMessage) -> bool:
        instance = self._instances.get(message.instance_id)
        if instance is None:
            return False

        logger.info(
            "Unity message received: instance_id=%s type=%s payload=%s",
            message.instance_id,
            message.type,
            message.payload,
        )

        if message.type == UnityToServerMessageType.HELLO:
            return True

        # Handle ready message
        if message.type == "ready":
            ready_id = None
            if isinstance(message.payload, dict):
                ready_id = message.payload.get("ready_id")
            if ready_id is not None:
                try:
                    await self.on_unity_ready(message.instance_id, int(ready_id))
                except (ValueError, TypeError):
                    logger.warning("Invalid ready_id: %s", ready_id)
            return True

        self._dispatcher.apply_message(instance, message)

        if message.type in {
            UnityToServerMessageType.TEST_COMPLETED,
            UnityToServerMessageType.TEST_FAILED,
        }:
            logger.info("Auto-stopping Unity process: instance_id=%s", instance.id)
            await self._send_shutdown(instance.id)
            await self.stop_instance(instance.id, force=True)

        return True

    def on_agent_start_result(self, message: AgentMessage) -> None:
        if message.instance_id is None:
            return
        instance = self._instances.get(message.instance_id)
        if instance is None:
            return
        success = bool(message.payload.get("success"))
        if success:
            instance.process_id = message.payload.get("process_id")
            instance.launch_command = message.payload.get("launch_command", instance.launch_command)
            instance.state = UnityInstanceState.WAITING_FOR_CONNECTION
            if self._agent_registry is not None:
                self._agent_registry.mark_slot_running(instance.agent_id or "", instance.project_slot_id or "", instance.id)
        else:
            instance.state = UnityInstanceState.FAILED
            instance.error_message = message.payload.get("error", "agent launch failed")
            instance.end_time = datetime.now()
            self._release_agent_slot(instance)
            self._archive_if_terminal(instance)

    async def on_agent_process_exited(self, message: AgentMessage) -> None:
        if message.instance_id is None:
            return
        instance = self._instances.get(message.instance_id)
        if instance is None:
            return
        instance.exit_code = message.payload.get("exit_code")
        if instance.state not in TERMINAL_STATES:
            instance.state = UnityInstanceState.STOPPED if instance.exit_code == 0 else UnityInstanceState.FAILED
            instance.end_time = datetime.now()
        self._release_agent_slot(instance)
        self._archive_if_terminal(instance)

    def _release_agent_slot(self, instance: UnityInstance) -> None:
        if instance.launch_target != "agent" or self._agent_registry is None:
            return
        self._agent_registry.release_slot(instance.agent_id, instance.project_slot_id, instance.id)

    async def _send_shutdown(self, instance_id: str) -> None:
        websocket = self._registry.get(instance_id)
        if websocket is None:
            return

        try:
            shutdown = UnityMessage(
                instance_id=instance_id,
                type=ServerToUnityMessageType.SHUTDOWN,
            )
            await websocket.send_json(shutdown.model_dump(mode="json"))
        except Exception:
            logger.warning("Failed to send shutdown to Unity: instance_id=%s", instance_id, exc_info=True)

    def on_unity_disconnected(self, instance_id: str) -> None:
        instance = self._instances.get(instance_id)
        self._registry.unregister(instance_id)
        if instance:
            if instance.state not in {
                UnityInstanceState.COMPLETED,
                UnityInstanceState.FAILED,
                UnityInstanceState.STOPPED,
            }:
                instance.state = UnityInstanceState.DISCONNECTED
            self._archive_if_terminal(instance)
        logger.info("Unity disconnected: instance_id=%s", instance_id)

    def _archive_if_terminal(self, instance: UnityInstance) -> None:
        if instance.state not in TERMINAL_STATES or instance.id not in self._instances:
            return

        # Group instance: wait for entire group to complete
        if instance.group_id:
            group = self._groups.get(instance.group_id)
            if group is None:
                # orphan group instance 鈥?just clean up
                logger.warning("Orphan group instance cleaned up: instance_id=%s", instance.id)
                del self._instances[instance.id]
                return

            # Check if all instances in the group are terminal
            all_terminal = True
            group_instances: list[UnityInstance] = []
            for inst_id in group.instance_ids:
                inst = self._instances.get(inst_id)
                if inst is not None:
                    group_instances.append(inst)
                    if inst.state not in TERMINAL_STATES:
                        all_terminal = False

            if all_terminal and len(group_instances) == len(group.instance_ids):
                # Archive entire group
                self._history_store.archive_group(group.id, group.name, group_instances)
                for inst in group_instances:
                    if inst.id in self._instances:
                        del self._instances[inst.id]
                if group.id in self._groups:
                    del self._groups[group.id]
                logger.info("Group fully terminated and archived: group_id=%s", group.id)
            # If not all terminal, keep instance in memory
            return

    def _sanitize_custom_args(self, args: dict[str, str | int | float | bool]) -> dict[str, str | int | float | bool]:
        sanitized: dict[str, str | int | float | bool] = {}
        for key, value in args.items():
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", key):
                raise ValueError(f"Invalid custom arg key: {key}")
            if key in {"instanceId", "serverUrl"}:
                raise ValueError(f"Custom arg key is reserved: {key}")
            sanitized[key] = value
        return sanitized

    def _new_instance_id(self) -> str:
        return f"unity-{uuid4().hex[:8]}"

    def _new_group_id(self) -> str:
        return f"group-{uuid4().hex[:8]}"
