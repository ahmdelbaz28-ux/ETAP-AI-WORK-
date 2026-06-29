import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.testclient import TestClient
from api.websocket import SCADALiveFeed
WS_PATH = "/ws/scada/live"

feed = SCADALiveFeed()
app = FastAPI()

@app.websocket(WS_PATH)
async def _ws(websocket: WebSocket):
    await feed.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        print('Caught WebSocketDisconnect, calling feed.disconnect')
        feed.disconnect(websocket)

client = TestClient(app)
with client.websocket_connect(WS_PATH) as ws:
    pass
print('After context block, feed.active_connections length:', len(feed.active_connections))
print('Feed active connections list:', feed.active_connections)
