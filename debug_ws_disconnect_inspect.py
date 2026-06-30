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
with client.websocket_connect(WS_PATH) as ws1:
    print('inside block, len(active_connections)', len(feed.active_connections))
    # Not sending any messages
    pass
# After exiting block
print('after block, len(active_connections)', len(feed.active_connections))
print('underlying list contents', list(feed.active_connections))
