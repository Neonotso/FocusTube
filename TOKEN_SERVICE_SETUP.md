# FocusTube Token Service Setup

This is the free personal-use backend for persistent YouTube login.

## What it does

- Runs on Ryan's always-on Mac
- Stores the YouTube refresh token locally in `.secrets/youtube_tokens.json`
- Lets FocusTube ask for a fresh access token when the short-lived one expires

## Files

- `scripts/focustube_token_service.py`
- `scripts/requirements.txt`

## Required secret file

Create:

- `FocusTube/.secrets/google_oauth_client.json`

This should be the **OAuth client secret JSON** downloaded from Google Cloud Console for the web app.

## Install deps

Use a venv or install locally:

```bash
cd FocusTube
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
```

## Run locally

```bash
cd FocusTube
source .venv/bin/activate
FOCUSTUBE_ALLOWED_ORIGIN=https://focustube.web.app \
FOCUSTUBE_TOKEN_HOST=127.0.0.1 \
FOCUSTUBE_TOKEN_PORT=8787 \
python scripts/focustube_token_service.py
```

## OAuth redirect URI

The service expects this redirect URI by default:

```text
https://focustube.web.app/oauth/callback
```

If you change host/port, also update the redirect URI in Google Cloud Console.

## Endpoints

- `GET /health`
- `GET /auth/start`
- `GET /oauth/callback`
- `POST /token/refresh`
- `POST /token/revoke`

## Current limitation

This is best for personal use on Ryan's own devices / network setup.
Public multi-user sharing should come later, after quota strategy is improved.
