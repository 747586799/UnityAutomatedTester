from app.agents.models import AgentMessage


def make_agent_command(
    command_type: str,
    agent_id: str,
    instance_id: str | None = None,
    request_id: str | None = None,
    payload: dict | None = None,
) -> AgentMessage:
    return AgentMessage(
        type=command_type,
        agent_id=agent_id,
        instance_id=instance_id,
        request_id=request_id,
        payload=payload or {},
    )
