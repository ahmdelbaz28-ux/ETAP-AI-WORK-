"""
WebSocket endpoint for real-time SCADA data streaming.
Provides live updates to connected clients without requiring refresh.
"""
import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import List

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

    async def connect(self, websocket: WebSocket):
        """Add a new WebSocket connection to the active connections list."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"New WebSocket connection established. Total connections: {len(self.active_connections)}")

        # Start broadcasting if not already running
        if not self.is_broadcasting:
            self.is_broadcasting = True
            self.broadcast_task = asyncio.create_task(self._broadcast_loop())

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection from the active connections list."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket connection closed. Total connections: {len(self.active_connections)}")

        # Stop broadcasting if no active connections
        if len(self.active_connections) == 0 and self.is_broadcasting:
            self.is_broadcasting = False
            if self.broadcast_task:
                self.broadcast_task.cancel()

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a personal message to a specific WebSocket client."""
        if websocket.application_state == WebSocketState.CONNECTED:
            await websocket.send_text(message)

    async def broadcast_message(self, message: str):
        """Broadcast a message to all active WebSocket connections."""
        disconnected_clients = []

        for connection in self.active_connections:
            try:
                if connection.application_state == WebSocketState.CONNECTED:
                    await connection.send_text(message)
                else:
                    disconnected_clients.append(connection)
            except Exception as e:
                logger.error(f"Error sending message to WebSocket: {e}")
                disconnected_clients.append(connection)

        # Remove disconnected clients
        for client in disconnected_clients:
            self.disconnect(client)

    async def _generate_scada_data(self) -> dict:
        """Generate mock SCADA data for demonstration purposes.

        In a real implementation, this would connect to actual SCADA systems.
        """
        import random

        scada_data = {
            "timestamp": datetime.now(UTC).isoformat(),
            "measurements": {
                "bus_voltages": [
                    {"bus_id": "BUS_1", "voltage_kV": round(random.uniform(11.0, 12.5), 3), "angle_deg": round(random.uniform(-5, 5), 2)},
                    {"bus_id": "BUS_2", "voltage_kV": round(random.uniform(11.0, 12.5), 3), "angle_deg": round(random.uniform(-5, 5), 2)},
                    {"bus_id": "BUS_3", "voltage_kV": round(random.uniform(11.0, 12.5), 3), "angle_deg": round(random.uniform(-5, 5), 2)},
                ],
                "line_flows": [
                    {"line_id": "LINE_1_2", "mw": round(random.uniform(10, 100), 2), "mvar": round(random.uniform(5, 50), 2)},
                    {"line_id": "LINE_2_3", "mw": round(random.uniform(10, 100), 2), "mvar": round(random.uniform(5, 50), 2)},
                ],
                "generator_outputs": [
                    {"gen_id": "GEN_1", "mw": round(random.uniform(50, 200), 2), "mvar": round(random.uniform(20, 80), 2)},
                    {"gen_id": "GEN_2", "mw": round(random.uniform(50, 200), 2), "mvar": round(random.uniform(20, 80), 2)},
                ],
                "load_values": [
                    {"load_id": "LOAD_1", "mw": round(random.uniform(10, 50), 2), "mvar": round(random.uniform(5, 25), 2)},
                    {"load_id": "LOAD_2", "mw": round(random.uniform(10, 50), 2), "mvar": round(random.uniform(5, 25), 2)},
                ]
            },
            "alarms": [],
            "system_status": "NORMAL"
        }

        # Randomly add alarms occasionally
        if random.random() < 0.1:  # 10% chance of alarm
            scada_data["alarms"].append({
                "alarm_id": f"ALARM_{random.randint(1000, 9999)}",
                "timestamp": datetime.now(UTC).isoformat(),
                "severity": "WARNING" if random.random() < 0.7 else "CRITICAL",
                "description": f"Simulated alarm for equipment {random.choice(['Transformer', 'Breaker', 'Line'])}",
                "location": random.choice(["SUBSTATION_A", "SUBSTATION_B", "FEEDER_C"])
            })

        return scada_data

    async def _broadcast_loop(self):
        """Continuously broadcast SCADA data to all connected clients."""
        logger.info("Starting SCADA data broadcast loop")
        while self.is_broadcasting:
            try:
                # Generate fresh SCADA data
                scada_data = await self._generate_scada_data()

                # Broadcast to all clients
                message = json.dumps(scada_data, separators=(',', ':'))
                await self.broadcast_message(message)

                # Wait 1 second before next broadcast
                await asyncio.sleep(1)

            except asyncio.CancelledError:
                logger.info("SCADA broadcast loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in SCADA broadcast loop: {e}")
                await asyncio.sleep(5)  # Wait 5 seconds before retrying


# Initialize the SCADA feed
scada_feed = SCADALiveFeed()


async def scada_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time SCADA data."""
    await scada_feed.connect(websocket)
    try:
        # Keep the connection alive
        while True:
            # We don't expect to receive messages from clients in this implementation
            # Just keep the connection alive and send periodic updates
            data = await websocket.receive_text()
            # Optionally handle client messages if needed
            await scada_feed.send_personal_message(f"Ack: {data}", websocket)
    except WebSocketDisconnect:
        scada_feed.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        scada_feed.disconnect(websocket)
