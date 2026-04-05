# FocusTube

A minimal static web app for browsing YouTube with Shorts filtered out.

## Deploy

```bash
firebase deploy
```

## Token service

FocusTube uses a small local token backend on Ryan's Mac for YouTube OAuth refreshes.

- local service: `http://127.0.0.1:8787`
- Tailscale path: `https://ryans-mac-studio.tailed49b1.ts.net/focustube-token`
- launch agent label: `com.ryan.focustube-token-service`

### Automatic behavior

The token service is configured as a macOS LaunchAgent so it will:
- start automatically at login
- restart automatically if it crashes
- stay bound to port `8787`

LaunchAgent file:

```bash
~/Library/LaunchAgents/com.ryan.focustube-token-service.plist
```

Wrapper script:

```bash
/Users/ryantaylorvegh/.openclaw/workspace/FocusTube/scripts/restart_focustube_token_service.sh
```

### Useful Terminal commands

Restart manually:

```bash
launchctl kickstart -k gui/$(id -u)/com.ryan.focustube-token-service
```

Check status:

```bash
launchctl print gui/$(id -u)/com.ryan.focustube-token-service
```

Check local health:

```bash
curl http://127.0.0.1:8787/health
```

Check Tailscale-routed health:

```bash
curl https://ryans-mac-studio.tailed49b1.ts.net/focustube-token/health
```

View logs:

```bash
tail -f /Users/ryantaylorvegh/.openclaw/workspace/FocusTube/.secrets/focustube-token-service.log
tail -f /Users/ryantaylorvegh/.openclaw/workspace/FocusTube/.secrets/focustube-token-service.error.log
```

### Troubleshooting

If the browser shows a CORS error for `/focustube-token/token/refresh`, first check whether the backend is actually down.
A proxy/Tailscale `502` can look like a CORS problem from the browser side.

Healthy expected responses:

```bash
curl http://127.0.0.1:8787/health
curl https://ryans-mac-studio.tailed49b1.ts.net/focustube-token/health
```

Both should return:

```json
{"ok": true}
```

### Notes

- Static app hosted with Firebase Hosting
- Current token service allowed origin: `https://focustube.web.app`
