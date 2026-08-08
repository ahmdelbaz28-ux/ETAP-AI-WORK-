"""
Scenario 3: SCADA ← ETAP → GIS (Live)
======================================
بيانات SCADA حية من ETAP ADMS → MQTT → TimescaleDB → عرض实时ي.

Components:
  1. SCADA Bridge (OPC UA → MQTT) — runs continuously
  2. SCADA Consumer (MQTT → TimescaleDB + anomaly detection)
  3. Monitor (polls API for stats)

Usage:
  python scripts/scenarios/run_scenario_3.py --mode all --duration 300
  python scripts/scenarios/run_scenario_3.py --mode bridge
  python scripts/scenarios/run_scenario_3.py --mode consumer
  python scripts/scenarios/run_scenario_3.py --mode monitor --duration 60

Branch: feat/scenario-3-scada-live
Refs: PRODUCTION_PLAN/07_SCENARIO_3_SCADA_LIVE.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("scenario3")


async def run_bridge() -> None:
    """تشغيل SCADA bridge (OPC UA → MQTT)."""
    from etap_scada_bridge import ETAPScadaBridge

    bridge = ETAPScadaBridge()
    interval = float(os.environ.get("SCADA_BRIDGE_INTERVAL_SEC", "5"))

    try:
        await bridge.run(interval_sec=interval)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        await bridge.shutdown()


async def run_consumer() -> None:
    """تشغيل SCADA consumer (MQTT → TimescaleDB + anomaly detection)."""
    import ssl
    import paho.mqtt.client as mqtt

    # ─── Setup TimescaleDB ────────────────────────────────────────
    timescale_url = os.environ.get("TIMESCALE_URL", "")
    db_pool = None

    if timescale_url:
        try:
            import asyncpg

            db_pool = await asyncpg.create_pool(
                dsn=timescale_url, min_size=2, max_size=10, command_timeout=30,
            )

            async with db_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS timeseries.scada_tags (
                        timestamp TIMESTAMPTZ NOT NULL,
                        tag_id TEXT NOT NULL,
                        value DOUBLE PRECISION,
                        quality INT,
                        source TEXT,
                        trace_id TEXT
                    )
                """)
                await conn.execute("""
                    SELECT create_hypertable(
                        'timeseries.scada_tags', 'timestamp',
                        if_not_exists => TRUE
                    )
                """)
                await conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_scada_tags_tag_id_time
                    ON timeseries.scada_tags (tag_id, timestamp DESC)
                """)
            logger.info("✅ TimescaleDB pool ready")
        except Exception as exc:
            logger.warning("TimescaleDB setup failed: %s", exc)

    # ─── Anomaly thresholds ───────────────────────────────────────
    voltage_min = float(os.environ.get("ANOMALY_VOLTAGE_MIN", "0.95"))
    voltage_max = float(os.environ.get("ANOMALY_VOLTAGE_MAX", "1.05"))
    current_max = float(os.environ.get("ANOMALY_CURRENT_MAX", "1.20"))
    temp_max = float(os.environ.get("ANOMALY_TEMP_MAX", "85.0"))

    # ─── MQTT setup ───────────────────────────────────────────────
    broker_url = os.environ.get("MQTT_BROKER", "tcp://localhost:1883")
    username = os.environ.get("MQTT_USERNAME")
    password = os.environ.get("MQTT_PASSWORD")

    if broker_url.startswith(("tls://", "mqtts://")):
        use_tls = True
        host = broker_url.split("://", 1)[1].split(":")[0]
        port = 8883
    else:
        use_tls = False
        if "://" in broker_url:
            host = broker_url.split("://", 1)[1].split(":")[0]
        else:
            host = broker_url.split(":")[0]
        port = 1883

    client = mqtt.Client(protocol=mqtt.MQTTv5)
    if username:
        client.username_pw_set(username, password or "")
    if use_tls:
        client.tls_set(cert_reqs=ssl.CERT_REQUIRED)

    stats = {"messages_received": 0, "db_inserts": 0, "anomalies": 0}

    def on_message(mqtt_client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode())
            device_id = data.get("id")
            if not device_id:
                return

            stats["messages_received"] += 1

            if db_pool:
                async def store():
                    async with db_pool.acquire() as conn:
                        for field, value in data.items():
                            if field in ("id", "timestamp"):
                                continue
                            if not isinstance(value, (int, float)):
                                continue
                            tag_id = f"{device_id}.{field}"
                            ts = data.get("timestamp",
                                          datetime.now(timezone.utc).isoformat())
                            await conn.execute(
                                """INSERT INTO timeseries.scada_tags
                                   (timestamp, tag_id, value, quality, source)
                                   VALUES ($1, $2, $3, $4, $5)""",
                                ts, tag_id, float(value), 2, "etap_opcua",
                            )
                            stats["db_inserts"] += 1

                            # Anomaly check
                            anomaly = None
                            if "voltage" in field and (value < voltage_min or value > voltage_max):
                                anomaly = f"Voltage {value} outside [{voltage_min}, {voltage_max}]"
                            elif "current" in field and value > current_max:
                                anomaly = f"Current {value} exceeds {current_max}"
                            elif "temperature" in field and value > temp_max:
                                anomaly = f"Temperature {value}C exceeds {temp_max}C"

                            if anomaly:
                                stats["anomalies"] += 1
                                logger.warning("ANOMALY: %s - %s", tag_id, anomaly)

                try:
                    asyncio.get_event_loop().create_task(store())
                except RuntimeError:
                    pass

        except json.JSONDecodeError:
            logger.warning("Invalid JSON on %s", msg.topic)
        except Exception as exc:
            logger.exception("Message processing failed: %s", exc)

    client.on_message = on_message
    client.connect(host, port, 60)
    client.subscribe("project/power/+/status", qos=1)
    client.loop_start()
    logger.info("SCADA consumer subscribed to project/power/+/status")

    try:
        while True:
            await asyncio.sleep(60)
            logger.info("Consumer stats: %s", stats)
    except KeyboardInterrupt:
        logger.info("Stopping consumer...")
    finally:
        client.loop_stop()
        client.disconnect()
        if db_pool:
            await db_pool.close()


async def run_monitor(duration_sec: int) -> None:
    """مراقبة النظام لمدة محددة."""
    import httpx

    backend_url = os.environ.get("BACKEND_URL", "http://localhost:8000")
    start = time.time()

    while time.time() - start < duration_sec:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"{backend_url}/api/v1/scada/health")

            if r.status_code == 200:
                data = r.json()
                elapsed = time.time() - start
                print(f"[{elapsed:.0f}s] Tags: {data.get('tags_count', 0)}, "
                      f"Last msg: {data.get('last_message_age_sec', '?')}s ago, "
                      f"Alerts: {data.get('alerts_count', 0)}")
            else:
                logger.warning("Health check failed: %d", r.status_code)

        except Exception as exc:
            logger.warning("Monitor cycle failed: %s", exc)

        await asyncio.sleep(5)

    logger.info("Monitoring complete (%ds)", duration_sec)


async def run_all(duration_sec: int) -> None:
    """تشغيل bridge + consumer + monitor في نفس الوقت."""
    bridge_task = asyncio.create_task(run_bridge())
    consumer_task = asyncio.create_task(run_consumer())
    monitor_task = asyncio.create_task(run_monitor(duration_sec))

    try:
        await monitor_task
    finally:
        bridge_task.cancel()
        consumer_task.cancel()

        for task in (bridge_task, consumer_task):
            try:
                await task
            except asyncio.CancelledError:
                pass


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scenario 3: SCADA - ETAP - GIS (Live)",
    )
    parser.add_argument(
        "--mode", choices=["bridge", "consumer", "monitor", "all"],
        default="all",
        help="Component to run (default: all)",
    )
    parser.add_argument(
        "--duration", type=int, default=300,
        help="Duration in seconds for monitor/all mode (default: 300)",
    )
    args = parser.parse_args()

    if not os.environ.get("SCADA_OPC_ENDPOINT"):
        print("Set SCADA_OPC_ENDPOINT=opc.tcp://etap-adms:4840")
        sys.exit(1)
    if not os.environ.get("MQTT_BROKER"):
        print("Set MQTT_BROKER=tcp://localhost:1883")
        sys.exit(1)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    if args.mode == "bridge":
        asyncio.run(run_bridge())
    elif args.mode == "consumer":
        asyncio.run(run_consumer())
    elif args.mode == "monitor":
        asyncio.run(run_monitor(args.duration))
    elif args.mode == "all":
        asyncio.run(run_all(args.duration))


if __name__ == "__main__":
    main()
