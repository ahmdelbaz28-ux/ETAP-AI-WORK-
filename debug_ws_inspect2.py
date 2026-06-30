import time

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
        feed.disconnect(websocket)

client = TestClient(app)
with client.websocket_connect(WS_PATH) as ws:
    pass
# give some time for monitor to run
time.sleep(0.2)
# Using list.__iter__ to get raw underlying items (bypass overridden __iter__)
raw_items = list(list.__iter__(feed.active_connections))
print('Raw underlying list items count:', len(raw_items))
print('Filtered len (len(feed.active_connections)):', len(feed.active_connections))
