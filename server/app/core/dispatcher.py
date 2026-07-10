import json
from datetime import datetime

from app.core.models import UnityInstance
from app.core.states import UnityInstanceState
from app.protocol.messages import UnityMessage
from app.protocol.types import UnityToServerMessageType


class UnityMessageDispatcher:
    def apply_message(self, instance: UnityInstance, message: UnityMessage) -> None:
        message_type = message.type

        if message_type == UnityToServerMessageType.READY:
            instance.state = UnityInstanceState.CONNECTED
        elif message_type == UnityToServerMessageType.PROGRESS:
            percent = message.payload.get("percent")
            if isinstance(percent, int | float):
                instance.progress = float(percent)
        elif message_type == UnityToServerMessageType.LOG:
            instance.logs.append(
                {
                    "timestamp": message.timestamp,
                    "level": message.payload.get("level", "info"),
                    "message": message.payload.get("message", ""),
                }
            )
        elif message_type == UnityToServerMessageType.TEST_STARTED:
            instance.state = UnityInstanceState.RUNNING
        elif message_type == UnityToServerMessageType.TEST_COMPLETED:
            instance.state = UnityInstanceState.COMPLETED
            instance.progress = 1.0
            instance.result = self._merge_completed_result(instance.result, message.payload)
            instance.end_time = datetime.now()
            self._save_result(instance)
        elif message_type == UnityToServerMessageType.TEST_FAILED:
            instance.state = UnityInstanceState.FAILED
            instance.error_message = message.payload.get("error")
            instance.result = message.payload
            instance.end_time = datetime.now()
            self._save_result(instance)
        elif message_type == UnityToServerMessageType.HEARTBEAT:
            instance.last_heartbeat_time = datetime.now()

    def _merge_completed_result(self, current: dict | None, incoming: dict) -> dict:
        if not current:
            return incoming

        current_report = current.get("report")
        incoming_report = incoming.get("report")
        if current_report and incoming_report == "":
            merged = dict(incoming)
            merged["report"] = current_report
            return merged

        return incoming

    def _save_result(self, instance: UnityInstance) -> None:
        if instance.result_file is None or instance.result is None:
            return

        instance.result_file.parent.mkdir(parents=True, exist_ok=True)
        result = dict(instance.result)
        report = result.pop("report", None)

        if report is not None:
            (instance.result_file.parent / "report.txt").write_text(str(report), encoding="utf-8", newline="")
            result["report"] = report

        instance.result_file.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
