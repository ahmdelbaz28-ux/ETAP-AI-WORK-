import json
import pathlib

def main():
    yaml_content = """groups:
  - name: etap_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(request_errors_total[5m]) > 5
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: \"High error rate on ETAP services\"
          description: \"More than 5 errors per second over the last 5 minutes.\"
      - alert: HighLatency
        expr: histogram_quantile(0.99, request_latency_seconds_bucket) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: \"High request latency\"
          description: \"99th percentile latency > 2 seconds.\"
      - alert: SCADAUnavailable
        expr: scada_available == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: \"SCADA unavailable\"
          description: \"SCADA availability gauge is 0.\"
      - alert: DigitalTwinUnavailable
        expr: digital_twin_available == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: \"Digital Twin unavailable\"
          description: \"Digital Twin availability gauge is 0.\"
"""
    file_path = pathlib.Path(__file__).with_name("alerts.yml")
    file_path.write_text(yaml_content, encoding="utf-8")
    print(json.dumps({"created": True, "path": "alerts.yml"}))

if __name__ == "__main__":
    main()
