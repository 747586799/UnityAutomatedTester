from enum import StrEnum


class UnityInstanceState(StrEnum):
    CREATED = "created"
    STARTING = "starting"
    WAITING_FOR_CONNECTION = "waiting_for_connection"
    CONNECTED = "connected"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    STOPPING = "stopping"
    STOPPED = "stopped"
    DISCONNECTED = "disconnected"
