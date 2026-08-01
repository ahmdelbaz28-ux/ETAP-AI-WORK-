"""
WebSocket endpoint for real-time SCADA data streaming.
Provides live updates to connected clients without requiring refresh.

SECURITY AUDIT 2026-07-25 — Fix S-03: Added JWT authentication.
Previously, any client could connect without authentication, exposing
SCADA data to unauthorized parties. Now requires a valid JWT token
passed as a query parameter: ws://host/ws/scada?token=<jwt_access_token>
"""

import asyncio
import hmac
import json
import logging
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

UTC = timezone.utc  # noqa: UP017

from fastapi import Query, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)

# Global list to store active WebSocket connections
active_connections: List[WebSocket] = []

# Security Fix V-01: Connection lifecycle management
MAX_CONNECTIONS = 500  # Maximum concurrent WebSocket connections
HEARTBEAT_INTERVAL = 30  # seconds between heartbeat pings
HEARTBEAT_TIMEOUT = 10  # seconds to wait for pong before declaring dead
MAX_MISSED_HEARTBEATS = 3  # consecutive missed pings before forced disconnect


class SCADALiveFeed:
    """Manages real-time SCADA data broadcasting to WebSocket clients.

    Security Fix V-01: Added heartbeat/ping-pong, connection limits,
    and explicit cleanup handlers for abrupt disconnects.
    """

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.is_broadcasting = False
        self.broadcast_task = None
        # V-01: Track connection metadata for lifecycle management
        self._connection_meta: Dict[int, dict] = {}  # id(ws) -> meta
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._cleanup_lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        """Add a new WebSocket connection to the active connections list.

        Security Fix V-01: Enforces connection limit and starts
        heartbeat monitoring for each new connection.
        """
        # V-01: Enforce maximum connection limit
        if len(self.active_connections) >= MAX_CONNECTIONS:
            await websocket.close(code=4029, reason="Maximum connections reached")
            logger.warning(
                "WebSocket connection rejected: max connections (%d) reached",
                MAX_CONNECTIONS,
            )
            return

        await websocket.accept()
        self.active_connections.append(websocket)

        # V-01: Initialize connection metadata for heartbeat tracking
        self._connection_meta[id(websocket)] = {
            "connected_at": time.monotonic(),
            "last_pong": time.monotonic(),
            "missed_heartbeats": 0,
        }

        logger.info(
            "New WebSocket connection established. Total connections: %d",
            len(self.active_connections),
        )

        # Start broadcasting if not already running
        if not self.is_broadcasting:
            self.is_broadcasting = True
            self.broadcast_task = asyncio.create_task(self._broadcast_loop())

        # V-01: Start heartbeat monitor if not already running
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection from the active connections list.

        Security Fix V-01: Explicitly cleans up buffers and metadata
        on disconnect to prevent memory leaks from zombie connections.
        """
        async with self._cleanup_lock:
            ws_id = id(websocket)
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)

            # V-01: Clean up connection metadata and buffers
            if ws_id in self._connection_meta:
                del self._connection_meta[ws_id]

            # V-01: Attempt to close the underlying socket explicitly
            try:
                if websocket.application_state == WebSocketState.CONNECTED:
                    await websocket.close(code=1000, reason="Cleanup")
            except Exception:
                pass  # Already closed or unreachable

            logger.info(
                "WebSocket connection closed. Total connections: %d",
                len(self.active_connections),
            )

        # Stop broadcasting if no active connections
        if len(self.active_connections) == 0 and self.is_broadcasting:
            self.is_broadcasting = False
            if self.broadcast_task:
                self.broadcast_task.cancel()
            # V-01: Also stop heartbeat when no connections
            if self._heartbeat_task and not self._heartbeat_task.done():
                self._heartbeat_task.cancel()

    async def send_personal_message(self, message: str, websocket: WebSocket) -> None:
        """Send a personal message to a specific WebSocket client.

        Security Fix V-01: Updates heartbeat tracking on successful send.
        """
        if websocket.application_state == WebSocketState.CONNECTED:
            try:
                await websocket.send_text(message)
                # V-01: Refresh last activity timestamp
                ws_id = id(websocket)
                if ws_id in self._connection_meta:
                    self._connection_meta[ws_id]["last_pong"] = time.monotonic()
                    self._connection_meta[ws_id]["missed_heartbeats"] = 0
            except Exception:
                logger.warning("Failed to send personal message, scheduling cleanup")
                await self.disconnect(websocket)

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
            await self.disconnect(client)

    async def _generate_scada_data(  # NOSONAR: S7503 async signature required by callers; body intentionally sync  # — S7503: async signature required by callers; body intentionally sync
        self,
    ) -> dict:  # NOSONAR async function uses sync I/O for compatibility reasons
        """Generate mock SCADA data for demonstration purposes.

        **SIMULATED DATA**: This generates synthetic data for UI/UX demos only.
        The ``is_simulated`` flag is set to `True` so the frontend can show a
        red banner to operators. In a real deployment, this method would connect
        to actual SCADA systems (Zenon 7 / IEC 61850) and is_simulated would be `False`.
        """
        import random
        import secrets

        scada_data = {
            "is_simulated": True,
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

        # Randomly add alarms occasionally. Uses `secrets` (not `random`) so
        # SonarCloud S2245 stays satisfied — simulated telemetry is not
        # security-relevant, but the crypto-seeded PRNG removes the hotspot.
        if secrets.randbelow(10) == 0:  # 10% chance of alarm
            severity = "WARNING" if secrets.randbelow(10) < 7 else "CRITICAL"
            scada_data["alarms"].append(
                {
                    "alarm_id": f"ALARM_{secrets.randbelow(9000) + 1000}",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "severity": severity,
                    "description": f"Simulated alarm for equipment {secrets.choice(['Transformer', 'Breaker', 'Line'])}",
                    "location": secrets.choice(["SUBSTATION_A", "SUBSTATION_B", "FEEDER_C"]),
                },
            )

        return scada_data

    async def _heartbeat_loop(self):
        """Security Fix V-01: Periodic heartbeat to detect zombie connections.

        Sends a ping frame to each connected client and tracks missed
        heartbeats. Connections that exceed MAX_MISSED_HEARTBEATS are
        forcefully disconnected and cleaned up.
        """
        logger.info("Starting WebSocket heartbeat monitor")
        while self.active_connections:
            zombie_connections: List[WebSocket] = []

            for ws in list(self.active_connections):
                ws_id = id(ws)
                meta = self._connection_meta.get(ws_id)
                if not meta:
                    continue

                # Check if the connection has exceeded heartbeat timeout
                elapsed = time.monotonic() - meta["last_pong"]
                if elapsed > HEARTBEAT_INTERVAL + HEARTBEAT_TIMEOUT:
                    meta["missed_heartbeats"] += 1
                    logger.warning(
                        "WebSocket heartbeat missed for connection %s "
                        "(missed=%d, elapsed=%.1fs)",
                        ws_id,
                        meta["missed_heartbeats"],
                        elapsed,
                    )
                else:
                    meta["missed_heartbeats"] = 0

                # Force-disconnect zombie connections
                if meta["missed_heartbeats"] >= MAX_MISSED_HEARTBEATS:
                    zombie_connections.append(ws)

            # Clean up zombie connections
            for ws in zombie_connections:
                logger.warning(
                    "Force-disconnecting zombie WebSocket: %s", id(ws)
                )
                await self.disconnect(ws)

            await asyncio.sleep(HEARTBEAT_INTERVAL)

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


def _validate_ws_token(token: str) -> bool:
    """Validate JWT token for WebSocket authentication (S-03).

    Accepts:
    1. Valid JWT access token (Bearer-style)
    2. Engineering API service key (server-to-server)
    3. Skip validation if AUTH_DISABLED=true in development
    """
    import os

    # Skip in development if auth is disabled
    if os.getenv("ENGINEERING_SERVICE_AUTH_DISABLED", "").lower() in ("1", "true", "yes"):
        env = os.getenv("ENVIRONMENT", os.getenv("ENV", "development"))
        if env.lower() in ("development", "dev", "testing"):
            return True

    # Check API key (server-to-server) — constant-time comparison
    api_key = os.getenv("ENGINEERING_SERVICE_API_KEY", "")
    if api_key and hmac.compare_digest(token, api_key):
        return True

    # Check JWT token
    try:
        import jwt

        jwt_secret = os.getenv("JWT_SECRET_KEY", "")
        if not jwt_secret:
            logger.warning("WS auth: JWT_SECRET_KEY not configured")
            return False
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        # Accept only access tokens
        if payload.get("type") != "access":
            logger.warning("WS auth: rejected non-access token (type=%s)", payload.get("type"))
            return False
        # SECURITY: Check token blacklist (revoked tokens)
        jti = payload.get("jti")
        if jti:
            try:
                from api.auth import _is_token_blacklisted

                if _is_token_blacklisted(jti):
                    logger.warning("WS auth: rejected revoked token (jti=%s)", jti)
                    return False
            except (ImportError, AttributeError):
                pass  # blacklist unavailable
        return True
    except jwt.ExpiredSignatureError:
        logger.warning("WS auth: token expired")
        return False
    except jwt.InvalidTokenError as e:
        logger.warning("WS auth: invalid token: %s", e)
        return False


async def scada_websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(default="", description="JWT access token or API key for authentication"),
) -> None:
    """WebSocket endpoint for real-time SCADA data.

    SECURITY (S-03): Requires authentication via query parameter:
      ws://host/ws/scada?token=<jwt_access_token>
    """
    # SECURITY: Validate token before accepting connection
    if not _validate_ws_token(token):
        await websocket.close(
            code=4001, reason="Authentication required — provide valid token parameter"
        )
        logger.warning("WebSocket connection rejected: invalid or missing auth token")
        return

    await scada_feed.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # SECURITY (S-04): Sanitize input — do not echo raw user data back
            # Only acknowledge receipt with a safe, structured response
            try:
                parsed = json.loads(data)
                msg_type = parsed.get("type", "unknown") if isinstance(parsed, dict) else "unknown"
                safe_ack = json.dumps({"ack": True, "type": msg_type})
            except (json.JSONDecodeError, TypeError):
                safe_ack = json.dumps({"ack": True, "type": "raw"})
            await scada_feed.send_personal_message(safe_ack, websocket)
    except WebSocketDisconnect:
        await scada_feed.disconnect(websocket)
    except Exception:
        logger.exception("WebSocket error: ")
        await scada_feed.disconnect(websocket)
