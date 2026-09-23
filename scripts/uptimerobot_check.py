#!/usr/bin/env python3
"""
Inspect and configure UptimeRobot monitors.
"""
import json
import urllib.parse
import urllib.request

API_KEY = "u3475686-dcae0377ed9ef73751fce22a"

def get_monitors():
    url = "https://api.uptimerobot.com/v2/getMonitors"
    payload = urllib.parse.urlencode({
        "api_key": API_KEY,
        "format": "json",
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/x-www-form-urlencoded"
    })
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

if __name__ == "__main__":
    data = get_monitors()
    print("Stat:", data.get("stat"))
    print("Pagination:", data.get("pagination"))
    monitors = data.get("monitors", [])
    print(f"Total Monitors: {len(monitors)}")
    for m in monitors:
        print("=" * 50)
        print("ID:           ", m.get("id"))
        print("Name:         ", m.get("friendly_name"))
        print("URL:          ", m.get("url"))
        print("Status:       ", m.get("status"), "(2 = Up, 9 = Down, 0 = Paused, 1 = Not checked)")
        print("Type:         ", m.get("type"), "(1 = HTTP, 2 = Keyword, 3 = Ping, 4 = Port)")
        print("Interval (s): ", m.get("interval"))
