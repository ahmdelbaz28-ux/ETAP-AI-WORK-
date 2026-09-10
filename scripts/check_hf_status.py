import json
import urllib.request

URL = "https://huggingface.co/api/spaces/ahmdelbaz28/AhmedETAP-Platform"
req = urllib.request.Request(URL)
resp = urllib.request.urlopen(req)
d = json.load(resp)
rt = d.get("runtime", {})
print(f"Stage: {rt.get('stage')}")
print(f"Error: {str(rt.get('errorMessage', ''))[:300]}")
print(f"SHA: {d.get('sha', '?')[:12]}")
