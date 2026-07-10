from datetime import datetime

from fastapi import WebSocket

from app.agents.models import (
    AgentCapability,
    AgentInfo,
    AgentProjectSlot,
    AgentProjectSlotState,
    AgentState,
    ProjectSlotReservation,
)


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentInfo] = {}
        self._connections: dict[str, WebSocket] = {}

    async def register(self, agent_id: str, websocket: WebSocket, payload: dict) -> AgentInfo:
        old_websocket = self._connections.get(agent_id)
        if old_websocket is not None and old_websocket is not websocket:
            await old_websocket.close(code=1008, reason="duplicate agent_id")
        now = datetime.now()
        slots = [AgentProjectSlot.model_validate(slot) for slot in payload.get("project_slots", [])]
        capabilities = AgentCapability(
            project_slots=slots,
        )
        running_count = sum(1 for slot in slots if slot.state == AgentProjectSlotState.RUNNING)
        info = AgentInfo(
            agent_id=agent_id,
            server_id=payload.get("server_id"),
            hostname=payload.get("hostname", ""),
            ip=payload.get("ip"),
            os=payload.get("os", ""),
            state=AgentState.BUSY if running_count >= len(slots) else AgentState.ONLINE,
            running_count=running_count,
            capabilities=capabilities,
            connected_time=now,
            last_heartbeat_time=now,
        )
        self._agents[agent_id] = info
        self._connections[agent_id] = websocket
        return info

    def disconnect(self, agent_id: str) -> None:
        self._connections.pop(agent_id, None)
        agent = self._agents.get(agent_id)
        if agent is None:
            return
        agent.state = AgentState.DISCONNECTED
        agent.running_count = 0
        for slot in agent.capabilities.project_slots:
            if slot.state != AgentProjectSlotState.IDLE:
                slot.state = AgentProjectSlotState.DISCONNECTED
                slot.occupied_by = None

    def heartbeat(self, agent_id: str, payload: dict) -> None:
        agent = self._agents.get(agent_id)
        if agent is None:
            return
        agent.last_heartbeat_time = datetime.now()
        running_count = int(payload.get("running_count", agent.running_count))
        agent.running_count = running_count
        agent.state = AgentState.BUSY if running_count >= len(agent.capabilities.project_slots) else AgentState.ONLINE

    def list_agents(self) -> list[AgentInfo]:
        return list(self._agents.values())

    def get_agent(self, agent_id: str) -> AgentInfo | None:
        return self._agents.get(agent_id)

    def get_connection(self, agent_id: str) -> WebSocket | None:
        return self._connections.get(agent_id)

    def reserve_slots(self, project_id: str, count: int) -> list[ProjectSlotReservation]:
        idle_by_agent: dict[str, list[AgentProjectSlot]] = {}
        for agent_id, agent in self._agents.items():
            if agent.state not in {AgentState.ONLINE, AgentState.BUSY} or agent_id not in self._connections:
                continue
            slots = [
                slot for slot in agent.capabilities.project_slots
                if slot.project_id == project_id and slot.state == AgentProjectSlotState.IDLE
            ]
            if slots:
                idle_by_agent[agent_id] = slots

        if sum(len(slots) for slots in idle_by_agent.values()) < count:
            raise ValueError(f"not enough idle project slots for project_id={project_id}, required={count}")

        reservations: list[ProjectSlotReservation] = []
        while len(reservations) < count:
            progressed = False
            for agent_id in sorted(idle_by_agent, key=lambda aid: len(idle_by_agent[aid]), reverse=True):
                slots = idle_by_agent[agent_id]
                if not slots:
                    continue
                slot = slots.pop(0)
                reservation = ProjectSlotReservation(
                    agent_id=agent_id,
                    project_id=slot.project_id,
                    slot_id=slot.slot_id,
                    unity_executable_path=slot.unity_executable_path,
                    project_path=slot.project_path,
                )
                reservations.append(reservation)
                progressed = True
                if len(reservations) >= count:
                    break
            if not progressed:
                break

        for reservation in reservations:
            self.mark_slot_reserved(reservation.agent_id, reservation.slot_id, "")
        return reservations

    def mark_slot_reserved(self, agent_id: str, slot_id: str, instance_id: str) -> None:
        slot = self._find_slot(agent_id, slot_id)
        if slot is None:
            return
        slot.state = AgentProjectSlotState.RESERVED
        slot.occupied_by = instance_id or None

    def mark_slot_running(self, agent_id: str, slot_id: str, instance_id: str) -> None:
        slot = self._find_slot(agent_id, slot_id)
        if slot is None:
            return
        slot.state = AgentProjectSlotState.RUNNING
        slot.occupied_by = instance_id
        self._recalc_agent_state(agent_id)

    def release_slot(self, agent_id: str | None, slot_id: str | None, instance_id: str | None = None) -> None:
        if not agent_id or not slot_id:
            return
        slot = self._find_slot(agent_id, slot_id)
        if slot is None:
            return
        if instance_id and slot.occupied_by and slot.occupied_by != instance_id:
            return
        slot.state = AgentProjectSlotState.IDLE
        slot.occupied_by = None
        self._recalc_agent_state(agent_id)

    def sync_slots(self, agent_id: str, project_slots: list[dict]) -> None:
        agent = self._agents.get(agent_id)
        if agent is None:
            return
        slots = [AgentProjectSlot.model_validate(slot) for slot in project_slots]
        agent.capabilities.project_slots = slots
        running_count = sum(1 for slot in slots if slot.state == AgentProjectSlotState.RUNNING)
        agent.running_count = running_count
        agent.state = AgentState.BUSY if running_count >= len(slots) else AgentState.ONLINE

    def _recalc_agent_state(self, agent_id: str) -> None:
        agent = self._agents.get(agent_id)
        if agent is None:
            return
        total = len(agent.capabilities.project_slots)
        running = sum(1 for s in agent.capabilities.project_slots if s.state == AgentProjectSlotState.RUNNING)
        agent.running_count = running
        agent.state = AgentState.BUSY if running >= total else AgentState.ONLINE

    def _find_slot(self, agent_id: str, slot_id: str) -> AgentProjectSlot | None:
        agent = self._agents.get(agent_id)
        if agent is None:
            return None
        for slot in agent.capabilities.project_slots:
            if slot.slot_id == slot_id:
                return slot
        return None
