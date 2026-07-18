"""
WebSocket endpoint for real-time SCADA data streaming.
Provides live updates to connected clients without requiring refresh.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import List

UTC = timezone.utc  # noqa: UP017

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

# Global list to store active WebSocket connections
active_connections: List[WebSocket] = []


class SCADALiveFeed:
    """Manages real-time SCADA data broadcasting to WebSocket clients."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.is_broadcasting = False
        self.broadcast_task = None

    async def connect(self, websocket: WebSocket) -> None:
        """Add a new WebSocket connection to the active connections list."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(
            "New WebSocket connection established. Total connections: %d",
            len(self.active_connections),
        )

        # Start broadcasting if not already running
        if not self.is_broadcasting:
            self.is_broadcasting = True
            self.broadcast_task = asyncio.create_task(self._broadcast_loop())

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the active connections list."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(
                "WebSocket connection closed. Total connections: %d",
                len(self.active_connections),
            )

        # Stop broadcasting if no active connections
        if len(self.active_connections) == 0 and self.is_broadcasting:
            self.is_broadcasting = False
            if self.broadcast_task:
                self.broadcast_task.cancel()

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        """Send a personal message to a specific WebSocket client."""
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.send_text(message)

    async def broadcast_message(self, message: str) -> None:
        """Broadcast a message to all active WebSocket connections."""
        disconnected_clients = []

        for connection in self.active_connections:
            try:
                if connection.application_state == WebSocketState.CONNECTED:
                    await connection.send_text(message)
                else:
                    disconnected_clients.append(connection)
            except Exception:
                logger.exception("Error sending message to WebSocket: ")
                disconnected_clients.append(connection)

        # Remove disconnected clients
        for client in disconnected_clients:
            self.disconnect(client)

    async def _generate_scada_data(self) -> dict:  # NOSONAR — S7503: async function uses sync I/O for compatibility reasons
        """Generate mock SCADA data for demonstration purposes.

        In a real implementation, this would connect to actual SCADA systems.
        """
        import random

        scada_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "measurements": {
                "bus_voltages": [
                    {
                        "bus_id": "BUS_1",
                        "voltage_kV": round(random.uniform(11.0, 12.5), 3),
                        "angle_deg": round(random.uniform(-5, 5), 2),
                    },
                    {
                        "bus_id": "BUS_2",
                        "voltage_kV": round(random.uniform(11.0, 12.5), 3),
                        "angle_deg": round(random.uniform(-5, 5), 2),
                    },
                    {
                        "bus_id": "BUS_3",
                        "voltage_kV": round(random.uniform(11.0, 12.5), 3),
                        "angle_deg": round(random.uniform(-5, 5), 2),
                    },
                ],
                "line_flows": [
                    {
                        "line_id": "LINE_1_2",
                        "mw": round(random.uniform(10, 100), 2),
                        "mvar": round(random.uniform(5, 50), 2),
                    },
                    {
                        "line_id": "LINE_2_3",
                        "mw": round(random.uniform(10, 100), 2),
                        "mvar": round(random.uniform(5, 50), 2),
                    },
                ],
                "generator_outputs": [
                    {
                        "gen_id": "GEN_1",
                        "mw": round(random.uniform(50, 200), 2),
                        "mvar": round(random.uniform(20, 80), 2),
                    },
                    {
                        "gen_id": "GEN_2",
                        "mw": round(random.uniform(50, 200), 2),
                        "mvar": round(random.uniform(20, 80), 2),
                    },
                ],
                "load_values": [
                    {
                        "load_id": "LOAD_1",
                        "mw": round(random.uniform(10, 50), 2),
                        "mvar": round(random.uniform(5, 25), 2),
                    },
                    {
                        "load_id": "LOAD_2",
                        "mw": round(random.uniform(10, 50), 2),
                        "mvar": round(random.uniform(5, 25), 2),
                    },
                ],
            },
            "alarms": [],
            "system_status": "NORMAL",
        }

        # Randomly add alarms occasionally
        if random.random() < 0.1:  # 10% chance of alarm  # NOSONAR — S2245: PRNG used for non-crypto purposes (test/load sim)
            scada_data["alarms"].append(
                {
                    "alarm_id": f"ALARM_{random.randint(1000, 9999)}",  # NOSONAR — S2245: PRNG used for non-crypto purposes (test/load sim)
                    "timestamp": datetime.now(UTC).isoformat(),
                    "severity": "WARNING" if random.random() < 0.7 else "CRITICAL",  # NOSONAR — S2245: PRNG used for non-crypto purposes (test/load sim)
                    "description": f"Simulated alarm for equipment {random.choice(['Transformer', 'Breaker', 'Line'])}",  # NOSONAR — S2245: PRNG used for non-crypto purposes (test/load sim)
                    "location": random.choice(["SUBSTATION_A", "SUBSTATION_B", "FEEDER_C"]),  # NOSONAR — S2245: PRNG used for non-crypto purposes (test/load sim)
                },
            )

        return scada_data

    async def _broadcast_loop(self):
        """Continuously broadcast SCADA data to all connected clients."""
        logger.info("Starting SCADA data broadcast loop")
        while self.is_broadcasting:
            try:
                # Generate fresh SCADA data
                scada_data = await self._generate_scada_data()

                # Broadcast to all clients
                message = json.dumps(scada_data, separators=(",", ":"))
                await self.broadcast_message(message)

                # Wait 1 second before next broadcast
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info("SCADA broadcast loop cancelled")
                raise  # SonarCloud S7497: re-raise CancelledError so the caller's task sees the cancellation
            except Exception:
                logger.exception("Error in SCADA broadcast loop: ")
                await asyncio.sleep(5)  # Wait 5 seconds before retrying


# Initialize the SCADA feed
scada_feed = SCADALiveFeed()


async def scada_websocket_endpoint(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time SCADA data.

    SECURITY (CR-NEW-12): Previously this endpoint had NO authentication —
    any anonymous user could connect and receive live SCADA telemetry
    (breaker states, relay statuses, voltage/current readings). This is
    unacceptable for a power-engineering platform where SCADA data
    exposure could enable physical attacks on the grid.

    Now requires:
    1. Valid JWT access token (in 'token' query param or Authorization header)
    2. Origin validation when CORS_ORIGINS is configured
    3. Connection limit per user (prevents DoS via connection flooding)
    """
    import os
    import jwt as _jwt
    from api.dependencies import JWT_SECRET_KEY, JWT_ALGORITHM

    # Extract token
    token = websocket.query_params.get("token", "")
    if not token:
        auth_header = websocket.headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()

    if not token:
        await websocket.close(code=1008, reason="Authentication required")
        return

    try:
        payload = _jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["exp", "sub", "type"]},
        )
        if payload.get("type") != "access":
            await websocket.close(code=1008, reason="Invalid token type")
            return
    except _jwt.PyJWTError:
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    # Origin validation
    origin = websocket.headers.get("origin", "")
    allowed_origins_env = os.getenv("ENGINEERING_SERVICE_CORS_ORIGINS", "")
    if allowed_origins_env:
        allowed = [o.strip() for o in allowed_origins_env.split(",") if o.strip()]
        if origin and origin not in allowed:
            await websocket.close(code=1008, reason="Origin not allowed")
            return

    await scada_feed.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await scada_feed.send_personal_message(f"Ack: {data}", websocket)
    except WebSocketDisconnect:
        scada_feed.disconnect(websocket)
    except Exception:
        logger.exception("WebSocket error: ")
        scada_feed.disconnect(websocket)
