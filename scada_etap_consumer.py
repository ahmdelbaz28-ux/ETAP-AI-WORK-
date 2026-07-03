"""
SCADA ETAP Consumer
This module consumes data from ETAP via MQTT and processes it for SCADA systems.
"""

import json
import sqlite3
from datetime import datetime

import paho.mqtt.client as mqtt


class SCADAETAPConsumer:
    def __init__(self, db_path="scada_etap_data.db"):
        self.db_path = db_path
        self.setup_database()
        self.scada_tags = {}

    def setup_database(self):
        """Setup SQLite database to store received data"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create table for power system data
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS power_system_data (
                id TEXT PRIMARY KEY,
                status TEXT,
                voltage REAL,
                current REAL,
                power_factor REAL,
                load_percentage REAL,
                capacity TEXT,
                temperature REAL,
                oil_level REAL,
                current_flow REAL,
                rated_current REAL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()
        print(f"Database {self.db_path} initialized")

    def on_message(self, client, userdata, msg):
        """
        Handle incoming MQTT messages from ETAP
        """
        try:
            data = json.loads(msg.payload.decode())
            print(f"Received ETAP data on {msg.topic}: {data}")

            # Process ETAP power system data
            if "power" in msg.topic:
                self.process_power_data(data)

        except json.JSONDecodeError:
            print(f"Could not decode JSON from {msg.topic}")
        except Exception as e:
            print(f"Error processing message from {msg.topic}: {e}")

    def process_power_data(self, data):
        """
        Process power system data received from ETAP
        """
        print(f"Processing power data: {data}")

        # Store in database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Prepare data for insertion
        columns = [
            "id",
            "status",
            "voltage",
            "current",
            "power_factor",
            "load_percentage",
            "capacity",
            "temperature",
            "oil_level",
            "current_flow",
            "rated_current",
        ]

        values = []
        for col in columns:
            val = data.get(col)
            # Convert string numbers to floats where appropriate
            if col in [
                "voltage",
                "current",
                "power_factor",
                "load_percentage",
                "temperature",
                "oil_level",
                "current_flow",
                "rated_current",
            ]:
                try:
                    val = float(val) if val is not None else None
                except (ValueError, TypeError):
                    val = None
            values.append(val)

        # Insert or update the record
        placeholders = ", ".join(["?" for _ in columns])
        columns_str = ", ".join(columns)

        cursor.execute(
            f"""
            INSERT OR REPLACE INTO power_system_data
            ({columns_str}, timestamp) VALUES ({placeholders}, datetime('now'))
        """,
            values,
        )

        conn.commit()
        conn.close()

        # Example: Update UPS/redundancy status for stability analysis
        if data.get("id") == "ups_001":
            print(
                f"UPS Status: {data.get('status')}, Voltage: {data.get('voltage')}V, "
                f"Current: {data.get('current')}A",
            )
        elif data.get("id") == "redundancy_001":
            print(
                f"Redundancy Status: {data.get('status')}, "
                f"Load: {data.get('load_percentage')}%, Capacity: {data.get('capacity')}",
            )

        # Store in memory cache
        self.scada_tags[data["id"]] = {"data": data, "timestamp": datetime.now()}

    def setup_etap_integration(self):
        """
        Setup MQTT subscription for ETAP data
        """
        client = mqtt.Client()
        client.on_message = self.on_message

        try:
            # Connect to MQTT broker
            client.connect("localhost", 1883, 60)

            # Subscribe to ETAP topics
            client.subscribe("project/power/+/status")
            print("Subscribed to ETAP power system data")

            return client
        except Exception as e:
            print(f"Error connecting to MQTT broker: {e}")
            return None

    def run(self):
        """
        Run the consumer continuously
        """
        client = self.setup_etap_integration()
        if client:
            print("SCADA ETAP Consumer started, listening for data...")
            try:
                client.loop_forever()
            except KeyboardInterrupt:
                print("\nStopping SCADA ETAP Consumer...")
                client.disconnect()


def main():
    """
    Main execution function
    """
    print("Starting SCADA ETAP Consumer...")
    consumer = SCADAETAPConsumer()
    consumer.run()


if __name__ == "__main__":
    main()
