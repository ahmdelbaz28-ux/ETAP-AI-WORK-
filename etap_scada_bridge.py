"""
ETAP SCADA Bridge
This module handles the integration between ETAP ADMS and SCADA systems via MQTT.
"""

import csv
import json
import os
from datetime import UTC, datetime

UTC = UTC

import paho.mqtt.client as mqtt


def export_power_system_data():
    """
    Export power system data (CSV/XML) from ETAP ADMS
    In a real scenario, this would interface with ETAP API
    """
    # Create directory if it doesn't exist
    os.makedirs("etap_export", exist_ok=True)

    # Mock data simulating ETAP ADMS output
    power_data = {
        "timestamp": datetime.now(UTC).isoformat(),
        "devices": [
            {
                "id": "ups_001",
                "status": "online",
                "voltage": 230.5,
                "current": 12.3,
                "power_factor": 0.95,
            },
            {
                "id": "redundancy_001",
                "status": "active",
                "load_percentage": 75.2,
                "capacity": "2MW",
            },
            {"id": "transformer_001", "status": "normal", "temperature": 65.2, "oil_level": 85.0},
            {"id": "breaker_001", "status": "closed", "current_flow": 45.6, "rated_current": 63.0},
        ],
    }

    # Export to CSV
    csv_path = "etap_export/power_system.csv"
    with open(csv_path, "w", newline="") as csvfile:
        fieldnames = [
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
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for device in power_data["devices"]:
            # Fill missing fields with None
            row = {field: device.get(field, None) for field in fieldnames}
            writer.writerow(row)

    print(f"ETAP power system data exported to {csv_path}")
    return power_data


def publish_to_mqtt(data):
    """
    Publish ETAP data to MQTT broker for consumption by SCADA systems
    """
    try:
        client = mqtt.Client()
        client.connect("localhost", 1883, 60)
        client.loop_start()

        # Publish power system status
        for device in data["devices"]:
            topic = f"project/power/{device['id']}/status"
            payload = json.dumps(device)
            client.publish(topic, payload)
            print(f"Published to {topic}: {payload}")

        # Stop the loop and disconnect
        client.loop_stop()
        client.disconnect()
        print("Data published to MQTT successfully")

    except Exception as e:
        print(f"Error publishing to MQTT: {e}")


def main():
    """
    Main execution function
    """
    print("Starting ETAP SCADA Bridge...")

    # Export power system data
    power_data = export_power_system_data()

    # Publish to MQTT
    publish_to_mqtt(power_data)

    print("ETAP SCADA Bridge execution completed")


if __name__ == "__main__":
    main()
