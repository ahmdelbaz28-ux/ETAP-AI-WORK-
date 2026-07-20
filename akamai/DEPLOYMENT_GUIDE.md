# AhmedETAP Platform — Akamai Edge Protection Deployment Guide

This guide walks you through deploying Akamai edge protection in front of the AhmedETAP Platform. The backend integration code is already committed to the repo (`api/akamai_protection.py`); this guide covers the Akamai-side configuration.

---

## Architecture

```
User (browser/curl)
    │
    ▼
┌──────────────────────────────────────────────────┐
│  Akamai Edge  (etap.ahmdelbaz28.com)             │
│                                                  │
│  • CDN caching (static assets: 1 year TTL)      │
│  • WAF (SQLi, XSS, path traversal, SSRF, ...)   │
│  • Bot Manager (detect + block/challenge bots)  │
│  • Rate Limiting (auth: 10/min, API: 300/min)   │
│  • API Protection (OpenAPI validation + JWT)    │
│  • Security Headers (HSTS, CSP, X-Frame, ...)   │
│  • DDoS Protection (always-on)                  │
│  • Origin Verify (injects X-Origin-Verify)      │
└──────────────────────────────────────────────────┘
    │  (TLS, with X-Origin-Verify header)
    ▼
┌──────────────────────────────────────────────────┐
│  HF Space Origin                                │
│  (ahmdelbaz28-ahmedetap-platform.hf.space)      │
│                                                  │
│  api/akamai_protection.py middleware:           │
│  • Verifies X-Origin-Verify (rejects bypass)    │
│  • Parses bot score / reputation                │
│  • Origin-side rate limiting (defense-in-depth) │
│  • Blocks high bot scores + bad reputation      │
└──────────────────────────────────────────────────┘
```

---

## Prerequisites

1. **Akamai account** with the following products enabled:
   - Property Manager (`prd_SPM`)
   - Web Application Firewall (`prd_WAF`)
   - Bot Manager (`prd_BOTMGR`)
   - API Protection (`prd_APIPROTECT`)
   - Kona Site Defender (for DDoS)

2. **Custom domain** (e.g., `etap.ahmdelbaz28.com`) with DNS control.

3. **Akamai {OPEN} API credentials** (for programmatic deployment):
   - Host: `xxxxxx.luna.akamaiapis.net`
   - Client token: `akab-xxxx-xxxx-xxxx`
   - Client secret: `xxxxxx`
   - Access token: `akab-xxxx-xxxx-xxxx`

4. **Generate the origin verification secret**:
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   # Example output: VpK3xN7mR9sQ2wE8tY5uI1oP6aA0bC4dF7gH2jK9lM3nO6pQ=
   ```
   Save this — you'll set it as `AKAMAI_ORIGIN_SECRET` on the HF Space.

---

## Step 1: Deploy the Akamai Property

### Option A: Via Akamai Control Center (GUI)

1. Log in to **Akamai Control Center** → **☰** → **Property** → **Properties**.
2. Click **New Property** → name it `ahmedetap-platform`.
3. Set **Origin** to `ahmdelbaz28-ahmedetap-platform.hf.space`, port 443, TLS enabled.
4. Import the rules from `akamai/property.json` (Property Manager → Import JSON).
5. Set the environment variable in the property:
   - `AKAMAI_ORIGIN_SECRET` = the secret you generated in Prerequisites.
6. Add the hostname: `etap.ahmdelbaz28.com` → edge hostname `ahmedetap-platform.akamai.net`.
7. Save → Activate on Staging → test → Activate on Production.

### Option B: Via Akamai {OPEN} API (programmatic)

```bash
# Install the Akamai CLI + Property Manager plugin
npm install -g akamai
akamai install property

# Set up credentials in ~/.edgerc
cat > ~/.edgerc << 'EOF'
[default]
host = xxxxxx.luna.akamaiapis.net
client_token = akab-xxxx-xxxx-xxxx
client_secret = xxxxxxxxxxxxxxxx
access_token = akab-xxxx-xxxx-xxxx
EOF

# Create the property from the JSON config
akamai property create --file akamai/property.json --name ahmedetap-platform

# Activate on production
akamai property activate --name ahmedetap-platform --network production
```

---

## Step 2: Configure DNS

Point your custom domain to the Akamai edge hostname:

### For `etap.ahmdelbaz28.com`:

| Record Type | Name | Value | TTL |
|-------------|------|-------|-----|
| CNAME | `etap` | `ahmedetap-platform.akamai.net` | 3600 |

**Do NOT** create an A record pointing directly to the HF Space IP — that would allow bypassing Akamai.

### Verify DNS propagation:
```bash
dig etap.ahmdelbaz28.com
# Should resolve to Akamai edge IPs (23.x.x.x or similar)
```

---

## Step 3: Enable WAF + Bot Manager

### WAF (Web Application Firewall)
1. Control Center → **Security** → **Application Security**.
2. Create a security configuration named `ahmedetap-waf`.
3. Attach it to the `ahmedetap-platform` property.
4. Enable the following managed rule sets:
   - **KRS 8.x** (latest Akamai managed rules)
   - **OWASP Top 10** rule set
   - **SQL Injection** rule set
   - **XSS** rule set
5. Import custom rules from `akamai/waf-custom-rules.json`.
6. Set action mode to **DENY** (not just DETECT) for production.

### Bot Manager
1. Control Center → **Security** → **Bot Manager**.
2. Create a bot management policy.
3. Import configuration from `akamai/bot-manager-config.json`.
4. Enable **Bot Score Forwarding** (sends `X-Akamai-Bot-Score` header to origin).

### API Protection
1. Control Center → **Security** → **API Protection**.
2. Import the OpenAPI spec from `https://ahmdelbaz28-ahmedetap-platform.hf.space/openapi.json`.
3. Import rules from `akamai/api-protection-config.json`.
4. Enable schema validation and JWT validation at the edge.

---

## Step 4: Set the Origin Secret on HF Space

The backend middleware (`api/akamai_protection.py`) checks the `X-Origin-Verify` header. Set the same secret you used in the Akamai property:

```python
# Run this to set the HF Space secret
# Replace YOUR_HF_TOKEN with your actual HuggingFace access token
# Replace YOUR_GENERATED_SECRET with: python3 -c "import secrets; print(secrets.token_urlsafe(32))"
from huggingface_hub import HfApi
api = HfApi(token='YOUR_HF_TOKEN')
api.add_space_secret(
    'ahmdelbaz28/AhmedETAP-Platform',
    'AKAMAI_ORIGIN_SECRET',
    'YOUR_GENERATED_SECRET'
)
print('Secret set. Restart the Space to apply.')
```

After setting the secret, **restart the HF Space**. The origin will now reject any request that doesn't carry the `X-Origin-Verify` header (i.e., requests that bypassed Akamai).

---

## Step 5: Test the Configuration

### Test 1: Verify Akamai is in the path
```bash
curl -sI https://etap.ahmdelbaz28.com/health | grep -i "server\|x-akamai"
# Should show: Server: AkamaiGHost
```

### Test 2: Verify direct origin access is blocked
```bash
curl -sI https://ahmdelbaz28-ahmedetap-platform.hf.space/api/v1/agents
# Should return 403 with "Direct origin access is not permitted"
# (After AKAMAI_ORIGIN_SECRET is set on the HF Space)
```

### Test 3: Verify WAF blocks SQL injection
```bash
curl -s "https://etap.ahmdelbaz28.com/api/v1/agents?id=1' OR '1'='1"
# Should return 403 (blocked by WAF SQL injection rule)
```

### Test 4: Verify rate limiting on auth endpoints
```bash
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST https://etap.ahmdelbaz28.com/api/v1/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"test","password":"wrong"}'
done
# Should start returning 429 after 10 requests/minute
```

### Test 5: Verify bot blocking
```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -A "sqlmap/1.0" \
  https://etap.ahmdelbaz28.com/api/v1/agents
# Should return 403 (blocked by user-agent blacklist)
```

### Test 6: Verify security headers
```bash
curl -sI https://etap.ahmdelbaz28.com/ | grep -iE "strict-transport|content-security|x-frame|x-content-type|referrer"
# Should show all security headers
```

---

## Step 6: Update Frontend API URL

Update the Vercel `VITE_API_URL` env var to point to the Akamai-protected domain:

```bash
# Update via Vercel API
curl -X PATCH "https://api.vercel.com/v9/projects/prj_WucHqc3lQDwYe0i3ykgWz7UR5E3I/env/{env_id}" \
  -H "Authorization: Bearer YOUR_VERCEL_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "VITE_API_URL",
    "value": "https://etap.ahmdelbaz28.com",
    "type": "plain",
    "target": ["production", "preview", "development"]
  }'
```

Rebuild the UI to bake in the new URL.

---

## Monitoring & Alerting

### Akamai Dashboard
- **Security → Events**: real-time WAF/Bot blocks
- **Performance → Traffic**: CDN cache hit ratio
- **API Protection → API Abuse**: detected abuse patterns

### SIEM Integration (recommended)
Forward Akamai security events to your SIEM:
1. Control Center → **Security** → **SIEM Integration**.
2. Configure the SIEM connector (Splunk, ELK, Datadog, etc.).
3. Use the `X-Akamai-Request-ID` header to correlate edge events with origin logs.

### Alert Thresholds
| Metric | Warning | Critical |
|--------|---------|----------|
| WAF blocks/min | > 50 | > 200 |
| Bot blocks/min | > 100 | > 500 |
| Origin 5xx rate | > 1% | > 5% |
| Cache hit ratio | < 80% | < 60% |
| Rate limit 429s/min | > 100 | > 500 |

---

## Files in this Directory

| File | Purpose |
|------|---------|
| `property.json` | Akamai Property Manager configuration (CDN + caching + origin verify + security headers) |
| `waf-custom-rules.json` | 10 custom WAF rules (JWT tampering, SSRF, credential stuffing, etc.) |
| `bot-manager-config.json` | Bot detection policy (scoring thresholds, allowed/blocked bots) |
| `api-protection-config.json` | API schema validation + per-user rate limiting + abuse detection |
| `DEPLOYMENT_GUIDE.md` | This file |

## Backend Code (already committed)

| File | Purpose |
|------|---------|
| `api/akamai_protection.py` | Origin-side middleware: verifies Akamai metadata, enforces bot/reputation blocking |
| `hf-space/app.py` | Integrates the Akamai middleware into the FastAPI app |

---

## Rollback

To disable Akamai protection (e.g., for debugging):

1. Remove `AKAMAI_ORIGIN_SECRET` from HF Space secrets (or set to empty).
2. Restart the HF Space.
3. The middleware becomes a no-op (logs Akamai metadata but doesn't block).

To fully remove Akamai:
1. Deactivate the property in Akamai Control Center.
2. Change DNS CNAME back to the HF Space URL.
3. Remove the `AKAMAI_ORIGIN_SECRET` HF Space secret.

---

## What I Need From You (Ahmed)

The backend code and Akamai configuration templates are done. To activate Akamai protection, I need:

1. **Akamai account confirmation**: Do you have an active Akamai contract with the products listed in Prerequisites? (Property Manager, WAF, Bot Manager, API Protection)

2. **Custom domain**: What domain do you want to use? (e.g., `etap.ahmdelbaz28.com`) — I need DNS access to set the CNAME.

3. **Akamai API credentials** (optional, if you want me to deploy programmatically): host + client token + client secret + access token. Without these, you'll deploy via the Control Center GUI using the JSON configs I prepared.

4. **Approval to set `AKAMAI_ORIGIN_SECRET`**: Once the Akamai property is active, I'll generate a secret and set it on the HF Space. This will block direct origin access — confirm you're ready for that.

Everything else I can do myself.
