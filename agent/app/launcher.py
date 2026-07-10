import asyncio
from pathlib import Path
from typing import Any

from app.models import AgentConfig


class ProcessRegistry:
    def __init__(self) -> None:
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    async def start_unity(self, instance_id: str, payload: dict[str, Any], config: AgentConfig) -> tuple[int, list[str]]:
        log_file = payload.get("log_file")
        args = self.build_command(instance_id, payload, config, Path(log_file) if log_file else None)
        process = await asyncio.create_subprocess_exec(*args)
        self._processes[instance_id] = process
        return process.pid or 0, args

    async def stop(self, instance_id: str, force: bool) -> int | None:
        process = self._processes.get(instance_id)
        if process is None:
            return None
        if process.returncode is None:
            if force:
                process.kill()
            else:
                process.terminate()
            await process.wait()
        self._processes.pop(instance_id, None)
        return process.returncode

    async def wait_for_exit(self, instance_id: str) -> int | None:
        process = self._processes.get(instance_id)
        if process is None:
            return None
        code = await process.wait()
        self._processes.pop(instance_id, None)
        return code

    def running_count(self) -> int:
        return sum(1 for process in self._processes.values() if process.returncode is None)

    def build_command(self, instance_id: str, payload: dict[str, Any], config: AgentConfig, log_file: Path | None) -> list[str]:
        args: list[str] = [
            payload["unity_executable_path"],
            "-batchmode",
            "-nographics",
            "-projectPath",
            payload["project_path"],
            "-executeMethod",
            payload["execute_method"],
            "-automatedTester.instanceId",
            instance_id,
            "-automatedTester.serverUrl",
            config.unity_server_url,
            "-automatedTester.agentId",
            config.agent_id,
        ]
        if log_file is not None:
            log_file.parent.mkdir(parents=True, exist_ok=True)
            args.extend(["-logFile", str(log_file)])
        for key, value in payload.get("args", {}).items():
            args.append(f"-automatedTester.{key}")
            args.append("true" if value is True else "false" if value is False else str(value))
        return args
