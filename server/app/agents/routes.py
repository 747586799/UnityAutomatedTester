from fastapi import APIRouter, Depends, HTTPException

from app.agents.models import AgentInfo
from app.agents.registry import AgentRegistry
from app.dependencies import get_agent_registry

router = APIRouter(prefix="/api/agents", tags=["agents"])


@router.get("", response_model=list[AgentInfo])
def list_agents(registry: AgentRegistry = Depends(get_agent_registry)) -> list[AgentInfo]:
    return registry.list_agents()


@router.get("/{agent_id}", response_model=AgentInfo)
def get_agent(agent_id: str, registry: AgentRegistry = Depends(get_agent_registry)) -> AgentInfo:
    agent = registry.get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent
