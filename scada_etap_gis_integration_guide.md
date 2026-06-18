# دليل دمج SCADA مع ETAP/QGIS/ArcGIS Pro

## 1) المتطلبات الأساسية (Pre-Requisites)

### أنظمة التشغيل المدعومة:
- Windows 10/11 (64-bit)
- Ubuntu 22.04 (64-bit)
- macOS 13+

### برمجيات مطلوبة:
- Python 3.10+ (لـ PyScada/JSON-SCADA)
- Java 17+ (لـ Scada-LTS)
- Go 1.21+ (لـ JSON-SCADA إذا استخدمت build من source)
- MongoDB 6.0+ (لـ JSON-SCADA)
- MQTT Broker: mosquitto 2.0+ أو EMQTT 5.0+
- ETAP 17.0+ (مع license فعال + module ADMS/SCADA)
- QGIS 3.34+ (LTR) + plugins: QuickMapServices, ArcGIS Connector
- ArcGIS Pro 3.2+ (مع license فعال + ArcPy)

### Ports المطلوبة:
- 1883 (MQTT)
- 5432 (PostgreSQL)
- 27017 (MongoDB)
- 8080 (SCADA web)

## 2) Backends SCADA المدعومة

| Backend | أحدث إصدار | لغة | ميزات رئيسية | connectors المدعومة |
|---|---|---|---|---|
| PyScada | 0.10.12+ | Python/Django | open source،EMS plugin, web dashboard | MQTT, OPC-UA, Modbus, HTTP, EMS |
| Scada-LTS | 2.8.5+ | Java | web-based, multi-platform،connectors | Modbus, OPC UA, MQTT, HTTP |
| JSON-SCADA | 1.2.3+ | Go/MongoDB | portable, scalable (up to 70k tags) | IEC 61850, IEC 60870, DNP3, OPC UA, MQTT |
| Node-RED + mqtt + dashboard | 4.0.0+ | JavaScript | lightweight, fluid dashboard | MQTT, HTTP, Modbus, OPC UA |

## 3) خطوات التثبيت (Setup Steps)

### A) PyScada (Python-based — recommended لـ ETAP/ADMS)

#### 1. تثبيت environment:
```bash
# Create virtual environment
python -m venv scada-env
source scada-env/bin/activate  # Linux/macOS
# أو scada-env\Scripts\activate  # Windows

# Upgrade pip and install PyScada
pip install --upgrade pip
pip install pyscada==0.10.12 pyscada-mqtt pyscada-opcua pyscada-modbus pyscada-ems
```

#### 2. إعداد MQTT Broker (mosquitto):
```bash
# Ubuntu
sudo apt install mosquitto mosquitto-clients
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

# Windows: download من https://mosquitto.org/download/، install، start service
```

#### 3. إعداد mosquitto.conf (اختياري):
```
port 1883
listener 1883
allow_anonymous true
```

#### 4. إعداد PyScada (config.yaml):
```yaml
mqtt:
  broker: mqtt://localhost:1883
  topics:
    - project/fire/alarm
    - project/fire/extinguish
    - project/power/status
tags:
  - id: detector_001
    zone: zone_A
    type: smoke
    coverage: 45m²
  - id: extinguisher_001
    zone: zone_A
    type: water_mist
    pressure: 10bar
    flow: 120L/min
ems:
  enabled: true
  energy_monitoring: true
```

#### 5. تشغيل PyScada:
```bash
pyscada-server start --config config.yaml
# web dashboard: http://localhost:8000
```

### B) Scada-LTS (Java-based — recommended لـ enterprise)

#### 1. تثبيت Java 17+:
```bash
# Ubuntu
sudo apt install openjdk-17-jdk

# Windows: download من https://www.oracle.com/java/technologies/downloads/، install
```

#### 2. تثبيت Scada-LTS:
```bash
wget https://github.com/SCADA-LTS/Scada-LTS/releases/download/v2.8.5/Scada-LTS-2.8.5.jar
java -jar Scada-LTS-2.8.5.jar
```

#### 3. إعداد connectors (في web dashboard):
- ModbusPal: enable + إعداد slave ID + register map
- OPC UA: enable + إعداد endpoint (opc.tcp://localhost:4840)
- MQTT: enable + إعداد broker (mqtt://localhost:1883) + topics

#### 4. إعداد tags (في JSON):
```json
{
  "id": "detector_001",
  "zone": "zone_A",
  "type": "smoke",
  "coverage": "45m²"
}
```

### C) JSON-SCADA (Go/MongoDB — recommended لـ scalable projects)

#### 1. تثبيت Go 1.21+ + MongoDB 6.0+:
```bash
# Ubuntu
sudo apt install go
sudo apt install mongodb
sudo systemctl enable mongodb
sudo systemctl start mongodb
```

#### 2. Build JSON-SCADA:
```bash
git clone https://github.com/riclolsen/json-scada
cd json-scada
go build
```

#### 3. إعداد config.json:
```json
{
  "mqtt": {
    "broker": "mqtt://localhost:1883",
    "topics": ["project/fire/alarm", "project/fire/extinguish"]
  },
  "mongodb": {
    "uri": "mongodb://localhost:27017",
    "db": "jsonscada"
  },
  "tags": [
    {"id": "detector_001", "zone": "zone_A", "type": "smoke"},
    {"id": "extinguisher_001", "zone": "zone_A", "type": "water_mist"}
  ]
}
```

#### 4. تشغيل:
```bash
./json-scada --config config.json
```

## 4) بروتوكول الربط (Integration Pipeline) — مع ETAP / QGIS / ArcGIS Pro

### A) ربط مع ETAP (ADMS/SCADA module)

#### 1. من ETAP:
```python
# etap_scada_bridge.py
import csv
import json
import paho.mqtt.client as mqtt

def export_power_system_data():
    """
    Export power system data (CSV/XML) from ETAP ADMS
    """
    # Mock function - in real scenario, this would interface with ETAP API
    power_data = {
        "timestamp": "2026-06-18T06:53:19Z",
        "devices": [
            {"id": "ups_001", "status": "online", "voltage": 230.5, "current": 12.3},
            {"id": "redundancy_001", "status": "active", "load_percentage": 75.2}
        ]
    }
    
    # Export to CSV
    with open('etap_export/power_system.csv', 'w', newline='') as csvfile:
        fieldnames = ['id', 'status', 'voltage', 'current', 'load_percentage']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for device in power_data['devices']:
            writer.writerow(device)
    
    return power_data

def publish_to_mqtt(data):
    """
    Publish ETAP data to MQTT broker for consumption by SCADA systems
    """
    client = mqtt.Client()
    client.connect("localhost", 1883, 60)
    
    # Publish power system status
    for device in data['devices']:
        topic = f"project/power/{device['id']}/status"
        payload = json.dumps(device)
        client.publish(topic, payload)
    
    client.disconnect()

# Main execution
if __name__ == "__main__":
    power_data = export_power_system_data()
    publish_to_mqtt(power_data)
    print("ETAP data exported and published to MQTT successfully")
```

#### 2. من PyScada/Scada-LTS/JSON-SCADA:
```python
# scada_etap_consumer.py
import json
import paho.mqtt.client as mqtt
import pandas as pd

def on_message(client, userdata, msg):
    """
    Handle incoming MQTT messages from ETAP
    """
    try:
        data = json.loads(msg.payload.decode())
        print(f"Received ETAP data on {msg.topic}: {data}")
        
        # Process ETAP power system data
        if 'power' in msg.topic:
            process_power_data(data)
    except json.JSONDecodeError:
        print(f"Could not decode JSON from {msg.topic}")

def process_power_data(data):
    """
    Process power system data received from ETAP
    """
    print(f"Processing power data: {data}")
    # Here you would typically update SCADA tags with ETAP data
    
    # Example: Update UPS/redundancy status for stability analysis
    if data.get('id') == 'ups_001':
        print(f"UPS Status: {data.get('status')}, Voltage: {data.get('voltage')}V")
    elif data.get('id') == 'redundancy_001':
        print(f"Redundancy Status: {data.get('status')}, Load: {data.get('load_percentage')}%")

def setup_etap_integration():
    """
    Setup MQTT subscription for ETAP data
    """
    client = mqtt.Client()
    client.on_message = on_message
    
    # Connect to MQTT broker
    client.connect("localhost", 1883, 60)
    
    # Subscribe to ETAP topics
    client.subscribe("project/power/+/status")
    
    print("Subscribed to ETAP power system data")
    return client

# Main execution
if __name__ == "__main__":
    client = setup_etap_integration()
    client.loop_forever()
```

#### 3. إعداد ETAP-MQTT (في ETAP ADMS):
```json
{
  "mqtt_broker": "mqtt://localhost:1883",
  "topics": ["project/power/status"],
  "tags": ["ups_001_status", "redundancy_001_status"],
  "connection_timeout": 30,
  "reconnect_interval": 5,
  "authentication": {
    "username": "etap_scada",
    "password": "${ETAP_MQTT_PASSWORD}"
  }
}
```

### B) ربط مع QGIS

#### 1. تثبيت plugins:
- QuickMapServices (لـ base maps)
- ArcGIS Connector (لـ ربط مع ArcGIS Pro)

#### 2. إعداد layer SCADA:
```python
# qgis_scada_layer.py
import json
import os
from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry, QgsPointXY
from qgis.PyQt.QtCore import QVariant

def create_scada_tags_geojson():
    """
    Create GeoJSON from SCADA tags for QGIS import
    """
    scada_tags = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [31.2357, 30.0444]  # Cairo coordinates as example
            },
            "properties": {
                "id": "detector_001",
                "zone": "zone_A",
                "type": "smoke",
                "coverage": "45m²",
                "status": "normal"
            }
        },
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [31.2457, 30.0544]
            },
            "properties": {
                "id": "extinguisher_001",
                "zone": "zone_A",
                "type": "water_mist",
                "pressure": "10bar",
                "flow": "120L/min",
                "status": "ready"
            }
        }
    ]
    
    geojson_data = {
        "type": "FeatureCollection",
        "features": scada_tags
    }
    
    # Create directory if it doesn't exist
    os.makedirs("scada_export", exist_ok=True)
    
    # Write GeoJSON file
    with open("scada_export/tags.geojson", "w") as f:
        json.dump(geojson_data, f, indent=2)
    
    print("SCADA tags exported to scada_export/tags.geojson")

def load_scada_layer_to_qgis():
    """
    Load SCADA tags layer into QGIS (conceptual - actual implementation would require QGIS Python API)
    """
    # Path to the GeoJSON file
    geojson_path = "scada_export/tags.geojson"
    
    # Create vector layer from GeoJSON
    layer = QgsVectorLayer(geojson_path, "SCADA_Tags", "ogr")
    
    if not layer.isValid():
        print("Layer failed to load!")
        return None
    
    print("SCADA tags layer loaded successfully")
    return layer

# Main execution
if __name__ == "__main__":
    create_scada_tags_geojson()
    print("SCADA tags created successfully")
```

#### 3. إعداد ArcGIS Connector (في QGIS):
```json
{
  "arcgis_url": "https://arcgis.yourcompany.com/rest/services",
  "service": "SCADA_Fire_Alarm",
  "layers": ["detectors", "extinguishers"],
  "sync_interval": 30,
  "credentials": {
    "username": "qgis_connector",
    "password": "${ARCGIS_CONNECTOR_PASSWORD}"
  }
}
```

### C) ربط مع ArcGIS Pro

#### 1. إعداد ArcPy script:
```python
# arcpro_scada_integration.py
import arcpy
import json
import paho.mqtt.client as mqtt
import os
from datetime import datetime

def create_feature_classes():
    """
    Create feature classes for SCADA data in ArcGIS Pro
    """
    # Set workspace
    arcpy.env.workspace = r"C:\temp\scada_geodatabase.gdb"
    
    # Create geodatabase if it doesn't exist
    gdb_path = r"C:\temp\scada_geodatabase.gdb"
    if not arcpy.Exists(gdb_path):
        arcpy.CreateFileGDB_management(r"C:\temp", "scada_geodatabase.gdb")
    
    # Create feature classes
    detectors_fc = arcpy.CreateFeatureclass_management(
        gdb_path, "detectors", "POINT", spatial_reference=arcpy.SpatialReference(4326)
    )
    
    extinguishers_fc = arcpy.CreateFeatureclass_management(
        gdb_path, "extinguishers", "POLYGON", spatial_reference=arcpy.SpatialReference(4326)
    )
    
    # Add fields to detectors
    arcpy.AddField_management(detectors_fc, "ID", "TEXT", field_length=50)
    arcpy.AddField_management(detectors_fc, "ZONE", "TEXT", field_length=50)
    arcpy.AddField_management(detectors_fc, "TYPE", "TEXT", field_length=50)
    arcpy.AddField_management(detectors_fc, "STATUS", "TEXT", field_length=50)
    arcpy.AddField_management(detectors_fc, "TIMESTAMP", "DATE")
    
    # Add fields to extinguishers
    arcpy.AddField_management(extinguishers_fc, "ID", "TEXT", field_length=50)
    arcpy.AddField_management(extinguishers_fc, "ZONE", "TEXT", field_length=50)
    arcpy.AddField_management(extinguishers_fc, "TYPE", "TEXT", field_length=50)
    arcpy.AddField_management(extinguishers_fc, "PRESSURE", "DOUBLE")
    arcpy.AddField_management(extinguishers_fc, "FLOW", "DOUBLE")
    arcpy.AddField_management(extinguishers_fc, "STATUS", "TEXT", field_length=50)
    arcpy.AddField_management(extinguishers_fc, "TIMESTAMP", "DATE")
    
    print("Feature classes created successfully")

def process_scada_tags(tags_geojson_path):
    """
    Process SCADA tags from GeoJSON and add to feature classes
    """
    with open(tags_geojson_path, 'r') as f:
        tags_data = json.load(f)
    
    gdb_path = r"C:\temp\scada_geodatabase.gdb"
    
    # Process each feature in the GeoJSON
    for feature in tags_data['features']:
        geometry = feature['geometry']
        properties = feature['properties']
        
        # Determine if it's a detector or extinguisher
        if properties['type'] == 'smoke':
            # Insert into detectors feature class
            with arcpy.da.InsertCursor(f"{gdb_path}\\detectors", 
                                     ["SHAPE@", "ID", "ZONE", "TYPE", "STATUS", "TIMESTAMP"]) as cursor:
                point = arcpy.Point(geometry['coordinates'][0], geometry['coordinates'][1])
                geom = arcpy.PointGeometry(point)
                cursor.insertRow([geom, properties['id'], properties['zone'], 
                                properties['type'], properties['status'], datetime.now()])
        
        elif properties['type'] in ['water_mist', 'foam', 'co2']:
            # For extinguishers, create a simple polygon around the point
            center_x, center_y = geometry['coordinates'][0], geometry['coordinates'][1]
            # Create a small square polygon (10m x 10m) as example
            polygon_points = [
                [center_x - 0.0001, center_y - 0.0001],
                [center_x + 0.0001, center_y - 0.0001],
                [center_x + 0.0001, center_y + 0.0001],
                [center_x - 0.0001, center_y + 0.0001],
                [center_x - 0.0001, center_y - 0.0001]  # Close the polygon
            ]
            
            array = arcpy.Array([arcpy.Point(*coords) for coords in polygon_points])
            polygon = arcpy.Polygon(array)
            
            with arcpy.da.InsertCursor(f"{gdb_path}\\extinguishers", 
                                     ["SHAPE@", "ID", "ZONE", "TYPE", "PRESSURE", "FLOW", "STATUS", "TIMESTAMP"]) as cursor:
                pressure = float(properties.get('pressure', '0').replace('bar', '')) if 'pressure' in properties else 0
                flow = float(properties.get('flow', '0').replace('L/min', '')) if 'flow' in properties else 0
                cursor.insertRow([polygon, properties['id'], properties['zone'], 
                                properties['type'], pressure, flow, properties['status'], datetime.now()])
    
    print(f"Processed {len(tags_data['features'])} SCADA tags")

def publish_gis_service():
    """
    Publish GIS service with SCADA layers
    """
    # Define connection file and service name
    connection_file = r"C:\temp\arcgis_connection.ags"
    service_name = "SCADA_Fire_Alarm"
    
    # Create service definition draft
    sddraft_path = f"C:\\temp\\{service_name}.sddraft"
    
    # Create SD draft from the feature dataset
    arcpy.mapping.CreateMapSDDraft(
        map_document=r"C:\temp\scada_map.mxd",  # This would be an actual map document
        out_sddraft=sddraft_path,
        service_name=service_name,
        server_type="ARCGIS_SERVER",
        connection_file_path=connection_file,
        copy_data_to_server=False,
        folder_name="SCADA_Integration",
        summary="SCADA Fire Alarm System Layers",
        tags="SCADA,Fire,Alarm,GIS"
    )
    
    print(f"Service definition draft created at {sddraft_path}")

# Main execution
if __name__ == "__main__":
    create_feature_classes()
    process_scada_tags("scada_export/tags.geojson")
    publish_gis_service()
    print("ArcGIS Pro SCADA integration completed successfully")
```

#### 2. إعداد MQTT client (في ArcPy):
```python
# arcpro_mqtt_client.py
import arcpy
import paho.mqtt.client as mqtt
import json
import threading
import time

class ArcGISProMQTTClient:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
        # SCADA tags storage
        self.scada_tags = {}
        
    def on_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")
        
        # Subscribe to SCADA topics
        client.subscribe("project/fire/alarm")
        client.subscribe("project/fire/extinguish")
        client.subscribe("project/power/+/status")
        print("Subscribed to SCADA topics")
        
    def on_message(self, client, userdata, msg):
        print(f"Received message on topic {msg.topic}: {msg.payload.decode()}")
        
        try:
            data = json.loads(msg.payload.decode())
            self.update_scada_tag(msg.topic, data)
        except json.JSONDecodeError:
            print(f"Could not decode JSON from {msg.topic}")
    
    def on_disconnect(self, client, userdata, rc):
        print("Disconnected from MQTT broker")
        
    def update_scada_tag(self, topic, data):
        """
        Update SCADA tag in ArcGIS Pro
        """
        # Store the tag data
        self.scada_tags[topic] = {
            'data': data,
            'timestamp': time.time()
        }
        
        # In a real implementation, this would update the corresponding feature in the geodatabase
        print(f"Updated SCADA tag {topic} with data: {data}")
        
        # Example: If it's a fire alarm, update the corresponding detector
        if 'fire/alarm' in topic:
            detector_id = topic.split('/')[-1]  # Extract detector ID from topic
            self.update_detector_status(detector_id, 'alarm_triggered')
    
    def update_detector_status(self, detector_id, status):
        """
        Update detector status in ArcGIS Pro feature class
        """
        gdb_path = r"C:\temp\scada_geodatabase.gdb"
        
        # Update the detector status
        with arcpy.da.UpdateCursor(f"{gdb_path}\\detectors", 
                                 ["ID", "STATUS", "TIMESTAMP"], 
                                 where_clause=f"ID = '{detector_id}'") as cursor:
            for row in cursor:
                row[1] = status  # Update status
                row[2] = time.strftime('%Y-%m-%d %H:%M:%S')  # Update timestamp
                cursor.updateRow(row)
        
        print(f"Updated detector {detector_id} status to {status}")
    
    def connect(self, broker_host="localhost", broker_port=1883):
        """
        Connect to MQTT broker
        """
        self.client.connect(broker_host, broker_port, 60)
        print("Starting MQTT client loop")
        self.client.loop_start()
    
    def disconnect(self):
        """
        Disconnect from MQTT broker
        """
        self.client.loop_stop()
        self.client.disconnect()
        print("MQTT client disconnected")

# Global instance for use in ArcGIS Pro
mqtt_client = None

def initialize_mqtt_client():
    """
    Initialize MQTT client for ArcGIS Pro
    """
    global mqtt_client
    if mqtt_client is None:
        mqtt_client = ArcGISProMQTTClient()
        mqtt_client.connect()
        print("MQTT client initialized for ArcGIS Pro")
    else:
        print("MQTT client already initialized")

def cleanup_mqtt_client():
    """
    Cleanup MQTT client when ArcGIS Pro closes
    """
    global mqtt_client
    if mqtt_client:
        mqtt_client.disconnect()
        mqtt_client = None
        print("MQTT client cleaned up")

# Example usage in ArcGIS Pro
if __name__ == "__main__":
    initialize_mqtt_client()
    
    # Keep the client running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        cleanup_mqtt_client()
```

## 5) التحقق والمراجعة (Validation)

### 1. التحقق من أن MQTT broker نشط:
```bash
# Check if MQTT broker is running
netstat -an | grep 1883  # Windows
# or
ss -tuln | grep 1883    # Linux
```

### 2. التحقق من أن PyScada/Scada-LTS/JSON-SCADA تشغيلها صحيح:
```bash
# Check if PyScada web dashboard is accessible
curl -I http://localhost:8000
```

### 3. التحقق من أن ETAP يستهلك tags power system بنجاح:
```python
# Test ETAP connectivity
import socket

def test_etap_connection():
    try:
        # Assuming ETAP ADMS is running on localhost port 8081
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', 8081))
        if result == 0:
            print("ETAP ADMS connection successful")
        else:
            print("ETAP ADMS connection failed")
        sock.close()
    except Exception as e:
        print(f"Error testing ETAP connection: {e}")

test_etap_connection()
```

### 4. التحقق من أن QGIS/ArcGIS Pro عرض layers SCADA بنجاح:
```python
# Test QGIS layer loading
import os

def test_qgis_layers():
    geojson_path = "scada_export/tags.geojson"
    if os.path.exists(geojson_path):
        print("SCADA tags GeoJSON file exists")
        with open(geojson_path, 'r') as f:
            import json
            data = json.load(f)
            print(f"Loaded {len(data['features'])} SCADA tags")
    else:
        print("SCADA tags GeoJSON file does not exist")

test_qgis_layers()
```

### 5. التحقق من أن endpoints MQTT/OPC-UA/Modbus نشطة:
```bash
# Test MQTT publish/subscribe
mosquitto_pub -h localhost -t "test/topic" -m "test message"
# In another terminal: mosquitto_sub -h localhost -t "test/topic"
```

## 6) مثال على تنفيذ كامل

### إنشاء نص برمجي لتشغيل النظام الكامل:

```bash
#!/bin/bash
# run_full_integration.sh

echo "Starting full SCADA-GIS integration..."

# Start MQTT broker
echo "Starting MQTT broker..."
mosquitto -d

# Wait for MQTT to start
sleep 3

# Start PyScada (if using)
echo "Starting PyScada..."
# source scada-env/bin/activate
# pyscada-server start --config config.yaml &

# Start ETAP bridge
echo "Starting ETAP bridge..."
python etap_scada_bridge.py &

# Start SCADA consumer
echo "Starting SCADA consumer..."
python scada_etap_consumer.py &

# Export SCADA tags for QGIS
echo "Exporting SCADA tags for QGIS..."
python qgis_scada_layer.py

# Process tags in ArcGIS Pro
echo "Processing SCADA tags in ArcGIS Pro..."
python arcpro_scada_integration.py

echo "Full integration started successfully!"
echo "Check http://localhost:8000 for PyScada dashboard"
echo "Check scada_export/tags.geojson for QGIS import"
```

## 7) ملاحظات إضافية

- جميع الملفات يجب أن تستخدم متغيرات البيئة لتخزين البيانات الحساسة
- يجب إضافة ملف [.gitignore](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/.gitignore) يحتوي على الملفات الحساسة
- يجب إنشاء ملف [requirements.txt](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/requirements.txt) يحتوي على جميع المكتبات المطلوبة
- يجب إنشاء ملف [Dockerfile](file:///c:/Users/Repair%20SC/Desktop/ETAP-AI-WORK--main/Dockerfile) لتسهيل النشر