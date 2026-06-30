"""
QGIS SCADA Layer
This module creates GeoJSON from SCADA tags for QGIS import.
"""

import json
import os
from datetime import datetime, timezone


def create_scada_tags_geojson():
    """
    Create GeoJSON from SCADA tags for QGIS import
    """
    scada_tags = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [31.2357, 30.0444],  # Cairo coordinates as example
            },
            "properties": {
                "id": "detector_001",
                "zone": "zone_A",
                "type": "smoke",
                "coverage": "45m²",
                "status": "normal",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [31.2457, 30.0544]},
            "properties": {
                "id": "extinguisher_001",
                "zone": "zone_A",
                "type": "water_mist",
                "pressure": "10bar",
                "flow": "120L/min",
                "status": "ready",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [31.2557, 30.0644]},
            "properties": {
                "id": "detector_002",
                "zone": "zone_B",
                "type": "heat",
                "coverage": "30m²",
                "status": "normal",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [31.2657, 30.0744]},
            "properties": {
                "id": "valve_001",
                "zone": "zone_C",
                "type": "control_valve",
                "status": "open",
                "pressure": "8bar",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        },
    ]

    geojson_data = {"type": "FeatureCollection", "features": scada_tags}

    # Create directory if it doesn't exist
    os.makedirs("scada_export", exist_ok=True)

    # Write GeoJSON file
    geojson_path = "scada_export/tags.geojson"
    with open(geojson_path, "w") as f:
        json.dump(geojson_data, f, indent=2)

    print(f"SCADA tags exported to {geojson_path}")
    return geojson_path


def validate_geojson_structure(geojson_path):
    """
    Validate the structure of the generated GeoJSON
    """
    try:
        with open(geojson_path) as f:
            data = json.load(f)

        # Basic validation
        assert data["type"] == "FeatureCollection"
        assert "features" in data
        assert len(data["features"]) > 0

        # Validate each feature
        for _i, feature in enumerate(data["features"]):
            assert "type" in feature
            assert feature["type"] == "Feature"
            assert "geometry" in feature
            assert "properties" in feature
            assert "coordinates" in feature["geometry"]
            assert len(feature["geometry"]["coordinates"]) == 2  # [lon, lat]

        print(f"GeoJSON validation passed for {len(data['features'])} features")
        return True

    except Exception as e:
        print(f"GeoJSON validation failed: {e}")
        return False


def create_qml_style_file():
    """
    Create a QML style file for QGIS symbology
    """
    qml_content = """<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28.9-Firenze" stylecategories="Symbology">
  <renderer-v2 type="categorizedSymbol" attr="type" enableorderby="0" forceraster="0">
    <categories>
      <category render="true" symbol="0" value="smoke" label="Smoke Detector"/>
      <category render="true" symbol="1" value="heat" label="Heat Detector"/>
      <category render="true" symbol="2" value="water_mist" label="Water Mist"/>
      <category render="true" symbol="3" value="control_valve" label="Control Valve"/>
    </categories>
    <symbols>
      <symbol alpha="1" clip_to_extent="1" type="marker" name="0" force_rhr="0">
        <layer enabled="1" pass="0" locked="0" class="SimpleMarker">
          <prop k="angle" v="0"/>
          <prop k="color" v="255,0,0,255"/>
          <prop k="horizontal_anchor_point" v="1"/>
          <prop k="joinstyle" v="bevel"/>
          <prop k="name" v="circle"/>
          <prop k="offset" v="0,0"/>
          <prop k="offset_map_unit_scale" v="3x:0,0,0,0,0,0"/>
          <prop k="offset_unit" v="MM"/>
          <prop k="outline_color" v="35,35,35,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0"/>
          <prop k="outline_width_map_unit_scale" v="3x:0,0,0,0,0,0"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="scale_method" v="diameter"/>
          <prop k="size" v="3"/>
          <prop k="size_map_unit_scale" v="3x:0,0,0,0,0,0"/>
          <prop k="size_unit" v="MM"/>
          <prop k="vertical_anchor_point" v="1"/>
        </layer>
      </symbol>
      <symbol alpha="1" clip_to_extent="1" type="marker" name="1" force_rhr="0">
        <layer enabled="1" pass="0" locked="0" class="SimpleMarker">
          <prop k="angle" v="0"/>
          <prop k="color" v="255,170,0,255"/>
          <prop k="horizontal_anchor_point" v="1"/>
          <prop k="joinstyle" v="bevel"/>
          <prop k="name" v="square"/>
          <prop k="offset" v="0,0"/>
          <prop k="offset_map_unit_scale" v="3x:0,0,0,0,0,0"/>
          <prop k="offset_unit" v="MM"/>
          <prop k="outline_color" v="35,35,35,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0"/>
          <prop k="outline_width_map_unit_scale" v="3x:0,0,0,0,0,0"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="scale_method" v="diameter"/>
          <prop k="size" v="3"/>
          <prop k="size_map_unit_scale" v="3x:0,0,0,0,0,0"/>
          <prop k="size_unit" v="MM"/>
          <prop k="vertical_anchor_point" v="1"/>
        </layer>
      </symbol>
      <symbol alpha="1" clip_to_extent="1" type="marker" name="2" force_rhr="0">
        <layer enabled="1" pass="0" locked="0" class="SimpleMarker">
          <prop k="angle" v="0"/>
          <prop k="color" v="0,0,255,255"/>
          <prop k="horizontal_anchor_point" v="1"/>
          <prop k="joinstyle" v="bevel"/>
          <prop k="name" v="triangle"/>
          <prop k="offset" v="0,0"/>
          <prop k="offset_map_unit_scale" v="3x:0,0,0,0,0,0"/>
          <prop k="offset_unit" v="MM"/>
          <prop k="outline_color" v="35,35,35,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0"/>
          <prop k="outline_width_map_unit_scale" v="3x:0,0,0,0,0,0"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="scale_method" v="diameter"/>
          <prop k="size" v="3"/>
          <prop k="size_map_unit_scale" v="3x:0,0,0,0,0,0"/>
          <prop k="size_unit" v="MM"/>
          <prop k="vertical_anchor_point" v="1"/>
        </layer>
      </symbol>
      <symbol alpha="1" clip_to_extent="1" type="marker" name="3" force_rhr="0">
        <layer enabled="1" pass="0" locked="0" class="SimpleMarker">
          <prop k="angle" v="0"/>
          <prop k="color" v="0,255,0,255"/>
          <prop k="horizontal_anchor_point" v="1"/>
          <prop k="joinstyle" v="bevel"/>
          <prop k="name" v="cross"/>
          <prop k="offset" v="0,0"/>
          <prop k="offset_map_unit_scale" v="3x:0,0,0,0,0,0"/>
          <prop k="offset_unit" v="MM"/>
          <prop k="outline_color" v="35,35,35,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0"/>
          <prop k="outline_width_map_unit_scale" v="3x:0,0,0,0,0,0"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="scale_method" v="diameter"/>
          <prop k="size" v="3"/>
          <prop k="size_map_unit_scale" v="3x:0,0,0,0,0,0"/>
          <prop k="size_unit" v="MM"/>
          <prop k="vertical_anchor_point" v="1"/>
        </layer>
      </symbol>
    </symbols>
    <source-symbol>
      <symbol alpha="1" clip_to_extent="1" type="marker" name="0" force_rhr="0">
        <layer enabled="1" pass="0" locked="0" class="SimpleMarker">
          <prop k="angle" v="0"/>
          <prop k="color" v="141,90,153,255"/>
          <prop k="horizontal_anchor_point" v="1"/>
          <prop k="joinstyle" v="bevel"/>
          <prop k="name" v="circle"/>
          <prop k="offset" v="0,0"/>
          <prop k="offset_map_unit_scale" v="3x:0,0,0,0,0,0"/>
          <prop k="offset_unit" v="MM"/>
          <prop k="outline_color" v="35,35,35,255"/>
          <prop k="outline_style" v="solid"/>
          <prop k="outline_width" v="0"/>
          <prop k="outline_width_map_unit_scale" v="3x:0,0,0,0,0,0"/>
          <prop k="outline_width_unit" v="MM"/>
          <prop k="scale_method" v="diameter"/>
          <prop k="size" v="2"/>
          <prop k="size_map_unit_scale" v="3x:0,0,0,0,0,0"/>
          <prop k="size_unit" v="MM"/>
          <prop k="vertical_anchor_point" v="1"/>
        </layer>
      </symbol>
    </source-symbol>
    <colorramp type="randomcolors" name="[source]"/>
    <rotation/>
    <sizescale/>
  </renderer-v2>
</qgis>"""

    # Write QML style file
    qml_path = "scada_export/scada_tags_style.qml"
    with open(qml_path, "w") as f:
        f.write(qml_content)

    print(f"QML style file created at {qml_path}")
    return qml_path


def main():
    """
    Main execution function
    """
    print("Creating SCADA tags for QGIS...")

    # Create GeoJSON
    geojson_path = create_scada_tags_geojson()

    # Validate GeoJSON
    if validate_geojson_structure(geojson_path):
        print("GeoJSON structure is valid")
    else:
        print("GeoJSON structure validation failed")

    # Create QML style file
    create_qml_style_file()

    print("SCADA tags creation completed successfully")


if __name__ == "__main__":
    main()
