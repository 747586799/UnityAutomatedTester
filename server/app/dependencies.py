from app.agents.registry import AgentRegistry
from app.automation.scheduler import AutoTaskScheduler
from app.automation.store import AutoTaskStore
from app.automation.template_store import AutomationTaskTemplateStore
from app.config import get_settings
from app.core.dispatcher import UnityMessageDispatcher
from app.core.launcher import UnityProcessLauncher
from app.core.manager import UnityInstanceManager
from app.core.registry import UnityConnectionRegistry
from app.runtime.history_store import HistoryStore
from app.runtime.launch_config import LaunchConfigStore
from app.runtime.workspace import RuntimeWorkspace
from pathlib import Path

settings = get_settings()
workspace = RuntimeWorkspace(settings.runtime_root)

_battle_log_path = Path(settings.battle_log_root) if settings.battle_log_root else None
history_store = HistoryStore(settings.runtime_root, battle_log_root=_battle_log_path)
launch_config_store = LaunchConfigStore(settings.runtime_root)
auto_task_store = AutoTaskStore(settings.runtime_root)
automation_template_store = AutomationTaskTemplateStore(settings.runtime_root)
registry = UnityConnectionRegistry()
agent_registry = AgentRegistry()
dispatcher = UnityMessageDispatcher()
launcher = UnityProcessLauncher(settings.server_url)
unity_manager = UnityInstanceManager(
    launcher=launcher,
    registry=registry,
    dispatcher=dispatcher,
    workspace=workspace,
    history_store=history_store,
    default_unity_executable=settings.default_unity_executable,
    agent_registry=agent_registry,
)
auto_task_scheduler = AutoTaskScheduler(auto_task_store, unity_manager, history_store)


def get_unity_manager() -> UnityInstanceManager:
    return unity_manager


def get_history_store() -> HistoryStore:
    return history_store


def get_agent_registry() -> AgentRegistry:
    return agent_registry


def get_launch_config_store() -> LaunchConfigStore:
    return launch_config_store


def get_auto_task_store() -> AutoTaskStore:
    return auto_task_store


def get_auto_task_scheduler() -> AutoTaskScheduler:
    return auto_task_scheduler


def get_automation_template_store() -> AutomationTaskTemplateStore:
    return automation_template_store
