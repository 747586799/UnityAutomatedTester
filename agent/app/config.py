import json
import socket
import sys
from pathlib import Path

from app.models import AgentConfig


def _config_path() -> Path:
    """返回可写配置文件的路径。

    打包为 exe 时: 放在 exe 同级目录下，用户可以直接编辑。
    源码运行时: 放在 agent/ 目录下。
    """
    if getattr(sys, "frozen", False):
        # PyInstaller 打包: exe 所在目录
        return Path(sys.executable).resolve().parent / "agent.config.json"
    return Path(__file__).resolve().parents[1] / "agent.config.json"


CONFIG_PATH = _config_path()


def load_config() -> AgentConfig:
    if not CONFIG_PATH.exists():
        # 尝试从 PyInstaller 内嵌资源读取默认配置（仅打包时生效）
        embedded = _try_load_embedded()
        if embedded is not None:
            # 首次使用，始终以本机 hostname 作为 agent_id
            config = embedded
            config.agent_id = socket.gethostname()
            save_config(config)
            return config
        config = AgentConfig()
        config.agent_id = socket.gethostname()
        save_config(config)
        return config
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    data.pop("max_parallel", None)
    config = AgentConfig.model_validate(data)
    return _with_default_agent_id(config)


def _try_load_embedded() -> AgentConfig | None:
    """PyInstaller 打包时尝试从 sys._MEIPASS 加载内嵌的默认配置。"""
    if not getattr(sys, "frozen", False):
        return None
    meipass = Path(sys._MEIPASS) / "agent.config.json"  # noqa
    if meipass.exists():
        try:
            data = json.loads(meipass.read_text(encoding="utf-8"))
            data.pop("max_parallel", None)
            return AgentConfig.model_validate(data)
        except Exception:
            return None
    return None


def _with_default_agent_id(config: AgentConfig) -> AgentConfig:
    if config.agent_id.strip():
        return config
    config.agent_id = socket.gethostname()
    return config


def save_config(config: AgentConfig) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(
        json.dumps(config.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
