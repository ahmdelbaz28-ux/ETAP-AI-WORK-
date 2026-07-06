"""
ETAP SCADA Bridge — Real OPC UA → MQTT
=======================================
يحل مشكلة أن الإصدار القديم كان يحتوي على بيانات hardcoded (Mock):
- ups_001, redundancy_001, transformer_001, breaker_001 (Mock devices)
- Cairo coordinates
- print() بدلاً من logging

هذا الـ implementation يستخدم:
- asyncua للاتصال بـ ETAP ADMS OPC UA server
- paho-mqtt للنشر على MQTT broker
- TLS + auth للأمان
- logging بدلاً من print
- Reconnection logic مع exponential backoff
- Stats tracking للـ monitoring

متطلبات:
    pip install asyncua paho-mqtt

متغيرات البيئة:
    SCADA_OPC_ENDPOINT=opc.tcp://etap-adms:4840
    SCADA_OPC_SECURITY=Basic256Sha256  (optional)
    SCADA_OPC_CERT_PATH=/certs/client.pem  (optional)
    SCADA_OPC_KEY_PATH=/certs/client.key  (optional)
    SCADA_OPC_USERNAME=etap_scada  (optional)
    SCADA_OPC_PASSWORD=***  (optional)
    MQTT_BROKER=tcp://localhost:1883  (or tls://mosquitto:8883)
    MQTT_USERNAME=etap_scada  (optional)
    MQTT_PASSWORD=***  (optional)
    SCADA_BRIDGE_INTERVAL_SEC=5  (default)

Branch: fix/scada-bridge-real-opcua
Refs: PRODUCTION_PLAN/01_SELF_CRITICISM.md §3.5 #20
Refs: PRODUCTION_PLAN/04_MOCK_TO_REAL_PLAN.md M1
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import ssl
import sys
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

# ─── OPC UA Node IDs لـ ETAP ADMS ─────────────────────────────────
# ⚠️ هذه قياسية لكن تحقق منها باستخدام UaExpert أو NodeID browser.
# قد تختلف حسب تركيب ETAP ADMS.
ETAP_OPC_NODES = {
    # UPS
    "ups_status": ("ns=2;s=ETAP.UPS.Status", "String"),
    "ups_voltage": ("ns=2;s=ETAP.UPS.Voltage", "Double"),
    "ups_current": ("ns=2;s=ETAP.UPS.Current", "Double"),
    "ups_power_factor": ("ns=2;s=ETAP.UPS.PowerFactor", "Double"),
    # Redundancy
    "redundancy_status": ("ns=2;s=ETAP.Redundancy.Status", "String"),
    "redundancy_load_pct": ("ns=2;s=ETAP.Redundancy.LoadPercentage", "Double"),
    "redundancy_capacity": ("ns=2;s=ETAP.Redundancy.Capacity", "String"),
    # Transformer
    "transformer_status": ("ns=2;s=ETAP.Transformer.Status", "String"),
    "transformer_temperature": ("ns=2;s=ETAP.Transformer.Temperature", "Double"),
    "transformer_oil_level": ("ns=2;s=ETAP.Transformer.OilLevel", "Double"),
    # Breaker
    "breaker_status": ("ns=2;s=ETAP.Breaker.Status", "String"),
    "breaker_current_flow": ("ns=2;s=ETAP.Breaker.CurrentFlow", "Double"),
    "breaker_rated_current": ("ns=2;s=ETAP.Breaker.RatedCurrent", "Double"),
    # Generator (لو موجود)
    "generator_status": ("ns=2;s=ETAP.Generator.Status", "String"),
    "generator_active_power": ("ns=2;s=ETAP.Generator.ActivePower", "Double"),
    "generator_reactive_power": ("ns=2;s=ETAP.Generator.ReactivePower", "Double"),
    "generator_frequency": ("ns=2;s=ETAP.Generator.Frequency", "Double"),
}


class ETAPScadaBridge:
    """
    Real SCADA Bridge: OPC UA → MQTT.

    يتصل بـ ETAP ADMS عبر OPC UA، يقرأ القيم بشكل دوري،
    وينشرها على MQTT broker للاستهلاك من قبل SCADA consumer.

    Features:
    - TLS + auth للأمان
    - Reconnection مع exponential backoff
    - Stats tracking (messages_published, messages_failed, opc_reconnects)
    - Graceful shutdown
    - logging بدلاً من print
    """

    def __init__(self) -> None:
        # OPC UA config
        self.opc_endpoint = os.environ.get("SCADA_OPC_ENDPOINT", "")
        if not self.opc_endpoint:
            raise RuntimeError("SCADA_OPC_ENDPOINT env var required")

        self.opc_security = os.environ.get("SCADA_OPC_SECURITY")
        self.opc_cert_path = os.environ.get("SCADA_OPC_CERT_PATH")
        self.opc_key_path = os.environ.get("SCADA_OPC_KEY_PATH")
        self.opc_username = os.environ.get("SCADA_OPC_USERNAME")
        self.opc_password = os.environ.get("SCADA_OPC_PASSWORD")

        # MQTT config
        self.mqtt_broker = os.environ.get("MQTT_BROKER", "tcp://localhost:1883")
        self.mqtt_username = os.environ.get("MQTT_USERNAME")
        self.mqtt_password = os.environ.get("MQTT_PASSWORD")

        # State
        self._opc_client = None
        self._mqtt_client = None
        self._running = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10

        # Stats
        self._stats = {
            "messages_published": 0,
            "messages_failed": 0,
            "opc_reconnects": 0,
            "last_message_time": None,
            "opc_nodes_read": 0,
            "opc_nodes_failed": 0,
        }

    # ─── OPC UA Connection ─────────────────────────────────────────

    async def connect_opc(self) -> None:
        """الاتصال بـ ETAP ADMS OPC UA server."""
        import asyncua

        logger.info("Connecting to OPC UA: %s", self.opc_endpoint)

        self._opc_client = asyncua.Client(
            url=self.opc_endpoint,
            timeout=10,
        )

        # Configure security if specified
        if self.opc_security and self.opc_cert_path and self.opc_key_path:
            try:
                security_policy = getattr(
                    asyncua.security_policies,
                    f"SecurityPolicy{self.opc_security}",
                )
                await self._opc_client.set_security(
                    security_policy,
                    self.opc_cert_path,
                    self.opc_key_path,
                )
                logger.info("OPC UA security configured: %s", self.opc_security)
            except AttributeError:
                logger.warning(
                    "Unknown security policy: %s — continuing without security",
                    self.opc_security,
                )
            except Exception as exc:
                logger.warning("Failed to configure OPC UA security: %s", exc)

        # Configure auth if specified
        if self.opc_username:
            self._opc_client.set_user(self.opc_username)
            self._opc_client.set_password(self.opc_password or "")

        # Connect with retry
        for attempt in range(3):
            try:
                await self._opc_client.connect()
                self._reconnect_attempts = 0
                logger.info("✅ Connected to OPC UA: %s", self.opc_endpoint)
                return
            except Exception as exc:
                logger.warning(
                    "OPC UA connect attempt %d/3 failed: %s",
                    attempt + 1, exc,
                )
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)  # exponential backoff

        raise RuntimeError(
            f"Failed to connect to OPC UA after 3 attempts: {self.opc_endpoint}"
        )

    # ─── MQTT Connection ───────────────────────────────────────────

    def connect_mqtt(self) -> None:
        """الاتصال بـ MQTT broker مع TLS + auth."""
        import paho.mqtt.client as mqtt

        # Parse broker URL
        broker_url = self.mqtt_broker
        if broker_url.startswith(("tls://", "mqtts://")):
            use_tls = True
            host = broker_url.split("://", 1)[1].split(":")[0]
            port = 8883
        elif broker_url.startswith(("tcp://", "mqtt://")):
            use_tls = False
            host = broker_url.split("://", 1)[1].split(":")[0]
            port = 1883
        else:
            use_tls = False
            host = broker_url.split(":")[0]
            port = broker_url.split(":")[1] if ":" in broker_url else 1883

        logger.info("Connecting to MQTT: %s:%d (TLS=%s)", host, port, use_tls)

        self._mqtt_client = mqtt.Client(protocol=mqtt.MQTTv5)

        if self.mqtt_username:
            self._mqtt_client.username_pw_set(
                self.mqtt_username,
                self.mqtt_password or "",
            )

        if use_tls:
            self._mqtt_client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
            self._mqtt_client.tls_insecure_set(False)

        # Set up callbacks
        self._mqtt_client.on_connect = self._on_mqtt_connect
        self._mqtt_client.on_disconnect = self._on_mqtt_disconnect
        self._mqtt_client.on_publish = self._on_mqtt_publish

        # Connect
        self._mqtt_client.connect(host, port, 60)
        self._mqtt_client.loop_start()

    def _on_mqtt_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("✅ Connected to MQTT broker")
        else:
            logger.error("❌ MQTT connect failed with code %d", rc)

    def _on_mqtt_disconnect(self, client, userdata, rc, properties=None):
        logger.warning("MQTT disconnected (rc=%d) — will auto-reconnect", rc)

    def _on_mqtt_publish(self, client, userdata, mid):
        self._stats["messages_published"] += 1
        self._stats["last_message_time"] = datetime.now(timezone.utc).isoformat()

    # ─── Data Reading ──────────────────────────────────────────────

    async def read_etap_nodes(self) -> dict[str, Any]:
        """قراءة كل الـ OPC UA nodes من ETAP ADMS."""
        if not self._opc_client:
            raise RuntimeError("OPC client not connected")

        data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "devices": [],
        }

        # Group by device type
        devices_by_type: dict[str, dict[str, Any]] = {}

        for tag, (node_id, _type) in ETAP_OPC_NODES.items():
            try:
                # Get node by ID
                node = await self._opc_client.nodes.objects.get_child(node_id)
                value = await node.read_value()

                # Parse tag: "ups_status" → prefix="ups", field="status"
                parts = tag.split("_", 1)
                if len(parts) == 2:
                    prefix, field = parts
                else:
                    prefix, field = "device", tag

                if prefix not in devices_by_type:
                    devices_by_type[prefix] = {"id": f"{prefix}_001"}
                devices_by_type[prefix][field] = value

                self._stats["opc_nodes_read"] += 1

            except Exception as exc:
                logger.warning("Failed to read OPC node %s: %s", node_id, exc)
                self._stats["opc_nodes_failed"] += 1
                # Don't fail the whole read for one node

        data["devices"] = list(devices_by_type.values())
        return data

    # ─── Publishing ────────────────────────────────────────────────

    def publish_to_mqtt(self, data: dict) -> None:
        """نشر البيانات على MQTT topics."""
        if not self._mqtt_client:
            raise RuntimeError("MQTT client not connected")

        for device in data.get("devices", []):
            device_id = device.get("id")
            if not device_id:
                continue

            topic = f"project/power/{device_id}/status"
            payload = json.dumps(device)

            try:
                info = self._mqtt_client.publish(topic, payload, qos=1)
                logger.debug("Published to %s (mid=%d)", topic, info.mid)
            except Exception as exc:
                logger.error("Failed to publish to %s: %s", topic, exc)
                self._stats["messages_failed"] += 1

    # ─── Main Loop ─────────────────────────────────────────────────

    async def run(self, interval_sec: float = 5.0) -> None:
        """
        الحلقة الرئيسية: قراءة OPC → نشر MQTT كل interval_sec ثواني.

        Args:
            interval_sec: الفترة بين القراءات (default: 5 sec)
        """
        self._running = True

        # Initial connections
        await self.connect_opc()
        self.connect_mqtt()

        logger.info("🚀 SCADA bridge running (interval=%.1fs)", interval_sec)

        try:
            while self._running:
                try:
                    # Read from OPC UA
                    data = await self.read_etap_nodes()

                    # Publish to MQTT
                    self.publish_to_mqtt(data)

                    # Reset reconnect counter on success
                    self._reconnect_attempts = 0

                except Exception as exc:
                    logger.exception("Bridge cycle failed: %s", exc)
                    self._stats["messages_failed"] += 1
                    self._reconnect_attempts += 1

                    if self._reconnect_attempts > self._max_reconnect_attempts:
                        logger.error(
                            "❌ Max reconnect attempts reached, exiting"
                        )
                        break

                    # Try to reconnect OPC UA
                    try:
                        if self._opc_client:
                            await self._opc_client.disconnect()
                        await asyncio.sleep(2)
                        await self.connect_opc()
                        self._stats["opc_reconnects"] += 1
                    except Exception as reconnect_exc:
                        logger.error("Reconnect failed: %s", reconnect_exc)

                await asyncio.sleep(interval_sec)

        finally:
            await self.shutdown()

    async def shutdown(self) -> None:
        """تنظيف الموارد عند الإغلاق."""
        logger.info("Shutting down SCADA bridge...")
        self._running = False

        if self._opc_client:
            try:
                await self._opc_client.disconnect()
                logger.info("OPC UA disconnected")
            except Exception as exc:
                logger.warning("OPC UA disconnect failed: %s", exc)

        if self._mqtt_client:
            try:
                self._mqtt_client.loop_stop()
                self._mqtt_client.disconnect()
                logger.info("MQTT disconnected")
            except Exception as exc:
                logger.warning("MQTT disconnect failed: %s", exc)

        logger.info("SCADA bridge stats: %s", self._stats)

    def stop(self) -> None:
        """إيقاف الحلقة الرئيسية (thread-safe)."""
        self._running = False

    def get_stats(self) -> dict:
        """إحصائيات الـ bridge للـ monitoring."""
        return self._stats.copy()


# ─── Backward Compatibility Functions ──────────────────────────────
# هذه الدوال تحافظ على التوافق مع الكود القديم الذي يستدعي
# export_power_system_data() و publish_to_mqtt() مباشرة.


async def export_power_system_data() -> dict[str, Any]:
    """
    قراءة بيانات النظام من ETAP ADMS عبر OPC UA.

    Backward compat wrapper for the old sync function.
    Returns the same dict shape: {"timestamp": ..., "devices": [...]}.

    Raises:
        RuntimeError: if SCADA_OPC_ENDPOINT is not set or connection fails.
    """
    bridge = ETAPScadaBridge()
    await bridge.connect_opc()
    try:
        return await bridge.read_etap_nodes()
    finally:
        if bridge._opc_client:
            await bridge._opc_client.disconnect()


def publish_to_mqtt(data: dict) -> None:
    """
    نشر البيانات على MQTT broker.

    Backward compat wrapper for the old sync function.
    Accepts the same dict shape: {"timestamp": ..., "devices": [...]}.

    Uses env vars MQTT_BROKER, MQTT_USERNAME, MQTT_PASSWORD.
    """
    import paho.mqtt.client as mqtt

    broker_url = os.environ.get("MQTT_BROKER", "tcp://localhost:1883")
    username = os.environ.get("MQTT_USERNAME")
    password = os.environ.get("MQTT_PASSWORD")

    # Parse broker URL
    if broker_url.startswith(("tls://", "mqtts://")):
        use_tls = True
        host = broker_url.split("://", 1)[1].split(":")[0]
        port = 8883
    elif broker_url.startswith(("tcp://", "mqtt://")):
        use_tls = False
        host = broker_url.split("://", 1)[1].split(":")[0]
        port = 1883
    else:
        use_tls = False
        host = broker_url.split(":")[0]
        port = broker_url.split(":")[1] if ":" in broker_url else 1883

    client = mqtt.Client(protocol=mqtt.MQTTv5)
    if username:
        client.username_pw_set(username, password or "")
    if use_tls:
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED)

    try:
        client.connect(host, port, 60)
        client.loop_start()

        for device in data.get("devices", []):
            device_id = device.get("id")
            if not device_id:
                continue
            topic = f"project/power/{device_id}/status"
            payload = json.dumps(device)
            info = client.publish(topic, payload, qos=1)
            logger.info("Published to %s (mid=%d)", topic, info.mid)

        client.loop_stop()
        client.disconnect()
        logger.info("Data published to MQTT successfully")

    except Exception as exc:
        logger.exception("Error publishing to MQTT: %s", exc)
        raise


# ─── Entry Point ───────────────────────────────────────────────────


async def _async_main() -> None:
    """Async entry point."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    bridge = ETAPScadaBridge()
    interval = float(os.environ.get("SCADA_BRIDGE_INTERVAL_SEC", "5"))

    try:
        await bridge.run(interval_sec=interval)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await bridge.shutdown()


def main() -> None:
    """Main execution function (backward compat entry point)."""
    if sys.platform == "win32":
        # Windows needs ProactorEventLoop for asyncua subprocess support
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        print("\nStopped by user")


if __name__ == "__main__":
    main()
