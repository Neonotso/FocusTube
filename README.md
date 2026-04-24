# FocusTube

A minimal static web app for browsing YouTube with Shorts filtered out.

## Deploy

```bash
firebase deploy
```

##quick Start

To start all services:

```bash
cd /Users/ryantaylorvegh/.openclaw/workspace-sally/FocusTube
source .venv/bin/activate
bash scripts/start_focustube_services.sh
```

## Accessing the App

The FocusTube web app serves via **HTTPS on port 443** using Tailscale Serve with automatic Let's Encrypt certificates.

- **App (HTTPS/Tailscale):** `https://ryans-mac-studio.tailed49b1.ts.net` (no port needed, HTTPS on 443)
- **Local reverse proxy (HTTP):** `http://127.0.0.1:80`
- **Local token service (HTTP):** `http://127.0.0.1:8787`
- **Tailscale app (HTTP):** `http://ryans-mac-studio.tailed49b1.ts.net` (Tailscale serves via HTTPS)
- **Tailscale token service:** `https://ryans-mac-studio.tailed49b1.ts.net/focustube-token`

**IMPORTANT:** The app is now accessible via HTTPS at `https://ryans-mac-studio.tailed49b1.ts.net` with no certificate warnings on iOS devices.

## Useful Terminal Commands

### Check Service Status
```bash
# Check Tailscale serve status
tailscale serve status

# Check token service health
curl http://127.0.0.1:8787/health

# Check HTTPS access (should return 200)
curl -sk https://ryans-mac-studio.tailed49b1.ts.net/ -o /dev/null -w '%{http_code}'
```

### Restart Services
```bash
# Stop all services
tailscale serve --https=443 off
pkill focustube_reverse_proxy.py
pkill focustube_token_service.py

# Start all services
bash scripts/start_focustube_services.sh
```

### View Logs
```bash
tail -f /tmp/focustube_token_service.log
tail -f /tmp/focustube_reverse_proxy.log
```

## Troubleshooting

If the browser shows a CORS error for `/focustube-token/token/refresh`, first check whether the backend is actually down.
A proxy/Tailscale `502` can look like a CORS problem from the browser side.

### Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| Cannot access app | Tailscale serve not running | `tailscale serve --https=443 http://127.0.0.1:80:bg` |
| `502 Bad Gateway` | Reverse proxy not running on port 80 | Start `focustube_reverse_proxy.py` |
| OAuth flow not working | Token service not running | Start `focustube_token_service.py` |
| Certificate warnings | Using HTTP instead of HTTPS | Use `https://ryans-mac-studio.tailed49b1.ts.net` |

### Health Check
Run these commands to verify all services are working:

```bash
# 1. Tailscale serve should show proxy config
tailscale serve status

# 2. Token service should respond
curl http://127.0.0.1:8787/health  # Should return: {"ok": true}

# 3. HTTPS access should return 200
curl -sk https://ryans-mac-studio.tailed49b1.ts.net/ -o /dev/null -w '%{http_code}'  # Should return: 200

# 4. Certificate should be from Let's Encrypt
openssl s_client -connect ryans-mac-studio.tailed49b1.ts.net:443 -servername ryans-mac-studio.tailed49b1.ts.net < /dev/null 2>/dev/null | openssl x509 -text -noout | grep "Issuer:"  # Should show: O=Let's Encrypt, CN=E8
```

## File Descriptions

| File | Purpose |
|------|---------|
| `SERVICES_SETUP.md` | Detailed documentation of all services and how to troubleshoot |
| `scripts/start_focustube_services.sh` | Script to start all services |
| `scripts/focustube_reverse_proxy.py` | Reverse proxy on port 80 |
| `scripts/focustube_token_service.py` | OAuth token service on port 8787 |
| `scripts/https_redirect.py` | (Legacy) HTTPS redirector - not currently used |

## Notes

- Static app served from `public/` directory
- Tailscale Serve handles HTTPS automatically using Let's Encrypt certificates
- Certificate is automatically renewed by Tailscale before expiration (90-day validity)
- For details on service architecture and troubleshooting, see `SERVICES_SETUP.md`
