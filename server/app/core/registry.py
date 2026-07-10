from fastapi import WebSocket


class UnityConnectionRegistry:
    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    def register(self, instance_id: str, websocket: WebSocket) -> None:
        self._connections[instance_id] = websocket

    def unregister(self, instance_id: str) -> None:
        self._connections.pop(instance_id, None)

    def get(self, instance_id: str) -> WebSocket | None:
        return self._connections.get(instance_id)

    def is_connected(self, instance_id: str) -> bool:
        return instance_id in self._connections
