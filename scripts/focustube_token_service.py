#!/usr/bin/env python3
import json
import os
import time
from pathlib import Path
from urllib.parse import parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

BASE_DIR = Path(__file__).resolve().parents[1]
SECRETS_DIR = BASE_DIR / '.secrets'
TOKENS_PATH = SECRETS_DIR / 'youtube_tokens.json'
CLIENT_SECRET_PATH = SECRETS_DIR / 'google_oauth_client.json'
STATE_PATH = SECRETS_DIR / 'oauth_state.json'
HOST = os.getenv('FOCUSTUBE_TOKEN_HOST', '127.0.0.1')
PORT = int(os.getenv('FOCUSTUBE_TOKEN_PORT', '8787'))
REDIRECT_URI = os.getenv('FOCUSTUBE_REDIRECT_URI', 'https://ryans-mac-studio.tailed49b1.ts.net/focustube-token/oauth/callback')
ALLOWED_ORIGIN = os.getenv('FOCUSTUBE_ALLOWED_ORIGIN', 'https://focustube.web.app')
SCOPES = ['https://www.googleapis.com/auth/youtube.force-ssl']

SECRETS_DIR.mkdir(parents=True, exist_ok=True)


def add_cors_headers(handler):
    origin = handler.headers.get('Origin') or ALLOWED_ORIGIN
    if origin == ALLOWED_ORIGIN:
        handler.send_header('Access-Control-Allow-Origin', origin)
    else:
        handler.send_header('Access-Control-Allow-Origin', ALLOWED_ORIGIN)
    handler.send_header('Vary', 'Origin')
    handler.send_header('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    handler.send_header('Access-Control-Max-Age', '86400')


def json_response(handler, code, payload):
    raw = json.dumps(payload).encode('utf-8')
    handler.send_response(code)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(raw)))
    add_cors_headers(handler)
    handler.end_headers()
    handler.wfile.write(raw)


def load_tokens():
    if not TOKENS_PATH.exists():
        return None
    return json.loads(TOKENS_PATH.read_text())


def save_tokens(data):
    TOKENS_PATH.write_text(json.dumps(data, indent=2))
    os.chmod(TOKENS_PATH, 0o600)


def build_flow(state=None, code_verifier=None):
    flow = Flow.from_client_secrets_file(
        str(CLIENT_SECRET_PATH),
        scopes=SCOPES,
        redirect_uri=REDIRECT_URI,
        state=state,
    )
    if code_verifier:
        flow.code_verifier = code_verifier
    return flow


def creds_from_saved(session_id=None):
    data = load_tokens()
    if not data:
        return None
    if session_id and data.get('session_id') and data.get('session_id') != session_id:
        return None
    creds = Credentials(
        token=data.get('token'),
        refresh_token=data.get('refresh_token'),
        token_uri='https://oauth2.googleapis.com/token',
        client_id=data.get('client_id'),
        client_secret=data.get('client_secret'),
        scopes=data.get('scopes', SCOPES),
    )
    return creds


class Handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(204)
        add_cors_headers(self)
        self.end_headers()

    def do_GET(self):
        if self.path == '/health':
            return json_response(self, 200, {'ok': True})

        if self.path.startswith('/auth/start'):
            if not CLIENT_SECRET_PATH.exists():
                return json_response(self, 500, {'error': f'Missing client secret file at {CLIENT_SECRET_PATH}'})
            qs = parse_qs(self.path.split('?', 1)[1] if '?' in self.path else '')
            session_id = qs.get('sessionId', [None])[0]

            # Generate PKCE code verifier for this flow
            import secrets
            code_verifier = secrets.token_urlsafe(64)

            flow = build_flow(code_verifier=code_verifier)
            auth_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                prompt='consent'
            )
            print('AUTH START', {'sessionId': session_id, 'state': state, 'redirectUri': REDIRECT_URI})
            STATE_PATH.write_text(json.dumps({
                'state': state,
                'sessionId': session_id,
                'codeVerifier': code_verifier
            }))
            if self.headers.get('Accept', '').find('application/json') >= 0 or self.path.find('format=json') >= 0:
                return json_response(self, 200, {'authUrl': auth_url})
            self.send_response(302)
            self.send_header('Location', auth_url)
            add_cors_headers(self)
            self.end_headers()
            return

        if self.path.startswith('/oauth/callback'):
            qs = self.path.split('?', 1)[1] if '?' in self.path else ''
            # For code exchange, we need to parse the query string and exchange directly
            if qs:
                parsed = parse_qs(qs)
                code = parsed.get('code', [None])[0]
                state = parsed.get('state', [None])[0]
                
                if code and state:
                    saved = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
                    saved_state = saved.get('state')
                    code_verifier = saved.get('codeVerifier')
                    
                    if state == saved_state:
                        try:
                            flow = build_flow(state=state, code_verifier=code_verifier)
                            flow.fetch_token(code=code, code_verifier=code_verifier)
                            creds = flow.credentials
                            save_tokens({
                                'token': creds.token,
                                'refresh_token': creds.refresh_token,
                                'client_id': creds.client_id,
                                'client_secret': creds.client_secret,
                                'scopes': creds.scopes,
                                'expiry': creds.expiry.isoformat() if creds.expiry else None,
                                'session_id': saved.get('sessionId'),
                            })
                            
                            self.send_response(200)
                            self.send_header('Content-Type', 'text/html; charset=utf-8')
                            self.end_headers()
                            self.wfile.write(b'<!DOCTYPE html><html><body><h2>Sign-in complete!</h2><p>You may close this window and return to FocusTube.</p><script>if(window.opener)window.opener.postMessage({type:"focustube-auth-complete"},"*");setTimeout(() => window.close(), 1500);</script></body></html>')
                            return
                        except Exception as e:
                            print('OAuth callback error:', e)
            
            # Fallback: serve callback HTML that can handle the query string via JS
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            html = f"""<html><body><h2>Finishing FocusTube sign-in...</h2><script>
(async function() {{
  try {{
    const qs = window.location.search.substring(1);
    const resp = await fetch('https://ryans-mac-studio.tailed49b1.ts.net/focustube-token/oauth/finalize', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
      body: qs
    }});
    if (!resp.ok) throw new Error('Finalize failed: ' + resp.status);
    if (window.opener) window.opener.postMessage({{ type: 'focustube-auth-complete' }}, '*');
    window.close();
    document.body.innerHTML = '<h2>FocusTube authorization complete.</h2><p>You can return to the app now.</p>';
  }} catch (e) {{
    document.body.innerHTML = '<h2>FocusTube sign-in failed.</h2><p>' + e.message + '</p>';
  }}
}})();
</script></body></html>"""
            self.wfile.write(html.encode('utf-8'))
            return

        return json_response(self, 404, {'error': 'Not found'})

    def do_POST(self):
        if self.path == '/oauth/finalize':
            length = int(self.headers.get('Content-Length', '0') or '0')
            raw = self.rfile.read(length).decode('utf-8') if length else ''
            print('OAUTH FINALIZE RAW', raw)
            qs = parse_qs(raw)
            code = qs.get('code', [None])[0]
            state = qs.get('state', [None])[0]
            saved = json.loads(STATE_PATH.read_text()) if STATE_PATH.exists() else {}
            saved_state = saved.get('state')
            session_id = saved.get('sessionId')
            code_verifier = saved.get('codeVerifier')
            print('OAUTH FINALIZE PARSED', {'code_present': bool(code), 'state': state, 'saved_state': saved_state, 'sessionId': session_id, 'has_code_verifier': bool(code_verifier)})
            if not code or not state or state != saved_state:
                return json_response(self, 400, {'error': 'Invalid OAuth finalize request'})
            flow = build_flow(state=state, code_verifier=code_verifier)
            flow.fetch_token(code=code, code_verifier=code_verifier)
            creds = flow.credentials
            save_tokens({
                'token': creds.token,
                'refresh_token': creds.refresh_token,
                'client_id': creds.client_id,
                'client_secret': creds.client_secret,
                'scopes': creds.scopes,
                'expiry': creds.expiry.isoformat() if creds.expiry else None,
                'session_id': session_id,
            })
            print('OAUTH FINALIZE OK', {'sessionId': session_id, 'has_refresh_token': bool(creds.refresh_token)})
            return json_response(self, 200, {'ok': True})

        if self.path == '/token/refresh':
            length = int(self.headers.get('Content-Length', '0') or '0')
            body = json.loads(self.rfile.read(length) or b'{}') if length else {}
            session_id = body.get('sessionId')
            creds = creds_from_saved(session_id=session_id)
            if not creds or not creds.refresh_token:
                return json_response(self, 401, {'error': 'No saved refresh token'})
            if not creds.valid or creds.expired:
                creds.refresh(Request())
                save_tokens({
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes,
                    'expiry': creds.expiry.isoformat() if creds.expiry else None,
                    'session_id': session_id,
                })
            expires_in = 3600
            if creds.expiry:
                expires_in = max(1, int((creds.expiry.timestamp() - time.time())))
            return json_response(self, 200, {
                'ok': True,
                'accessToken': creds.token,
                'expiresIn': expires_in,
            })

        if self.path == '/token/revoke':
            if TOKENS_PATH.exists():
                TOKENS_PATH.unlink()
            if STATE_PATH.exists():
                STATE_PATH.unlink()
            return json_response(self, 200, {'ok': True})

        return json_response(self, 404, {'error': 'Not found'})


if __name__ == '__main__':
    server = HTTPServer((HOST, PORT), Handler)
    print(f'FocusTube token service listening on http://{HOST}:{PORT}')
    print(f'Allowed origin: {ALLOWED_ORIGIN}')
    server.serve_forever()
