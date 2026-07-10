from pathlib import Path

import pytest

from app.core.dispatcher import UnityMessageDispatcher
from app.core.launcher import UnityProcessLauncher
from app.core.manager import UnityInstanceManager
from app.core.models import UnityInstance, UnityLaunchOptions
from app.core.registry import UnityConnectionRegistry
from app.core.states import UnityInstanceState
from app.protocol.messages import UnityMessage
from app.protocol.types import UnityToServerMessageType
from app.runtime.workspace import RuntimeWorkspace


@pytest.mark.asyncio
async def test_start_instance_requires_unity_executable(tmp_path: Path) -> None:
    manager = UnityInstanceManager(
        launcher=UnityProcessLauncher("ws://127.0.0.1:5100/ws/unity"),
        registry=UnityConnectionRegistry(),
        dispatcher=UnityMessageDispatcher(),
        workspace=RuntimeWorkspace(tmp_path),
    )

    instance = await manager.start_instance(UnityLaunchOptions(project_path="D:/Projects/Game"))

    assert instance.state == UnityInstanceState.FAILED
    assert instance.error_message == "unity_executable is required"


def test_duplicate_completed_with_empty_report_does_not_overwrite_existing_report(tmp_path: Path) -> None:
    dispatcher = UnityMessageDispatcher()
    instance = UnityInstance(
        id="unity-test",
        project_path="D:/Projects/Game",
        execute_method="Test.Run",
        result_file=tmp_path / "result.json",
    )

    dispatcher.apply_message(
        instance,
        UnityMessage(
            instance_id=instance.id,
            type=UnityToServerMessageType.TEST_COMPLETED,
            payload={
                "success": True,
                "passed": 0,
                "failed": 0,
                "duration_seconds": 0,
                "report": "full report",
            },
        ),
    )
    dispatcher.apply_message(
        instance,
        UnityMessage(
            instance_id=instance.id,
            type=UnityToServerMessageType.TEST_COMPLETED,
            payload={
                "success": True,
                "passed": 0,
                "failed": 0,
                "duration_seconds": 0,
                "report": "",
            },
        ),
    )

    assert instance.result is not None
    assert instance.result["report"] == "full report"
    assert '"report": "full report"' in instance.result_file.read_text(encoding="utf-8")
