from enum import StrEnum


class UnityToServerMessageType(StrEnum):
    HELLO = "hello"
    READY = "ready"
    PROGRESS = "progress"
    LOG = "log"
    TEST_STARTED = "test_started"
    TEST_COMPLETED = "test_completed"
    TEST_FAILED = "test_failed"
    HEARTBEAT = "heartbeat"
    CUSTOM_EVENT = "custom_event"


class ServerToUnityMessageType(StrEnum):
    START = "start"
    START_TEST = "start_test"
    STOP_TEST = "stop_test"
    EXECUTE = "execute"
    PING = "ping"
    CUSTOM_COMMAND = "custom_command"
    SHUTDOWN = "shutdown"
