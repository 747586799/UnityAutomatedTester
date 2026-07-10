import asyncio
from pathlib import Path
from typing import Any

from app.core.models import UnityLaunchOptions


class UnityProcessLauncher:
    def __init__(self, server_url: str) -> None:
        self.server_url = server_url
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    async def start(
        self,
        instance_id: str,
        options: UnityLaunchOptions,
        unity_executable: str,
        log_file: Path,
    ) -> int:
        args = self._build_args(instance_id, options, unity_executable, log_file)
        process = await asyncio.create_subprocess_exec(*args)
        self._processes[instance_id] = process
        return process.pid or 0

    async def stop(self, instance_id: str, force: bool = False) -> int | None:
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

    def get_process(self, instance_id: str) -> asyncio.subprocess.Process | None:
        return self._processes.get(instance_id)

    def build_command(
        self,
        instance_id: str,
        options: UnityLaunchOptions,
        unity_executable: str,
        log_file: Path,
    ) -> list[str]:
        return self._build_args(instance_id, options, unity_executable, log_file)

    def _build_args(
        self,
        instance_id: str,
        options: UnityLaunchOptions,
        unity_executable: str,
        log_file: Path,
    ) -> list[str]:
        args: list[str] = [
            unity_executable,
            "-batchmode",
            "-nographics",
            "-projectPath",
            options.project_path,
            "-executeMethod",
            options.execute_method,
            "-automatedTester.instanceId",
            instance_id,
            "-automatedTester.serverUrl",
            self.server_url,
            "-logFile",
            str(log_file),
        ]

        for key, value in options.args.items():
            args.append(f"-automatedTester.{key}")
            args.append(self._stringify_arg(value))

        return args

    def _stringify_arg(self, value: Any) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        return str(value)
