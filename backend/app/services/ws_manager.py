import json
from collections import defaultdict

from fastapi import WebSocket


class WebSocketConnectionManager:
    # WebSocket 连接管理器：按频道保存连接，用于推送任务进度和状态变更。
    def __init__(self) -> None:
        self.channels: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        # 接受客户端连接，并把连接加入对应频道。
        await websocket.accept()
        self.channels[channel].add(websocket)

    def disconnect(self, channel: str, websocket: WebSocket) -> None:
        if channel in self.channels:
            self.channels[channel].discard(websocket)
            if not self.channels[channel]:
                del self.channels[channel]

    async def broadcast(self, channel: str, payload: dict) -> None:
        # 向频道内的所有连接广播消息，失效连接会自动清理。
        dead: list[WebSocket] = []
        for ws in self.channels.get(channel, set()):
            try:
                await ws.send_text(json.dumps(payload, ensure_ascii=False))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(channel, ws)


ws_manager = WebSocketConnectionManager()
