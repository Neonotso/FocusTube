const admin = require('firebase-admin');
const { onRequest } = require('firebase-functions/v2/https');
const { defineSecret } = require('firebase-functions/params');
const { google } = require('googleapis');

admin.initializeApp();
const db = admin.firestore();

const GOOGLE_CLIENT_ID = defineSecret('GOOGLE_CLIENT_ID');
const GOOGLE_CLIENT_SECRET = defineSecret('GOOGLE_CLIENT_SECRET');
const GOOGLE_REDIRECT_URI = defineSecret('GOOGLE_REDIRECT_URI');
const FOCUSTUBE_SESSION_SECRET = defineSecret('FOCUSTUBE_SESSION_SECRET');

function addCors(res, origin = '*') {
  res.set('Access-Control-Allow-Origin', origin);
  res.set('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.set('Access-Control-Allow-Headers', 'Content-Type,X-FocusTube-Session');
  res.set('Access-Control-Allow-Credentials', 'true');
}

function makeOAuth2Client() {
  return new google.auth.OAuth2(
    GOOGLE_CLIENT_ID.value(),
    GOOGLE_CLIENT_SECRET.value(),
    GOOGLE_REDIRECT_URI.value()
  );
}

async function getSessionDoc(sessionId) {
  if (!sessionId) return null;
  const ref = db.collection('focustubeSessions').doc(sessionId);
  const snap = await ref.get();
  if (!snap.exists) return null;
  return { ref, data: snap.data() };
}

exports.exchangeYouTubeCode = onRequest(
  { secrets: [GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI] },
  async (req, res) => {
    addCors(res, req.headers.origin || '*');
    if (req.method === 'OPTIONS') return res.status(204).send('');
    if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

    try {
      const { code, sessionId } = req.body || {};
      if (!code || !sessionId) {
        return res.status(400).json({ error: 'Missing code or sessionId' });
      }

      const oauth2Client = makeOAuth2Client();
      const { tokens } = await oauth2Client.getToken(code);
      if (!tokens.refresh_token) {
        return res.status(400).json({ error: 'No refresh token returned by Google' });
      }

      oauth2Client.setCredentials(tokens);
      const youtube = google.youtube({ version: 'v3', auth: oauth2Client });
      const me = await youtube.channels.list({ part: ['snippet'], mine: true, maxResults: 1 });
      const channel = me.data.items?.[0];

      await db.collection('focustubeSessions').doc(sessionId).set({
        refreshToken: tokens.refresh_token,
        scope: tokens.scope || '',
        tokenType: tokens.token_type || 'Bearer',
        createdAt: admin.firestore.FieldValue.serverTimestamp(),
        updatedAt: admin.firestore.FieldValue.serverTimestamp(),
        channelId: channel?.id || '',
        channelTitle: channel?.snippet?.title || 'YouTube User'
      }, { merge: true });

      return res.json({
        ok: true,
        accessToken: tokens.access_token,
        expiresIn: tokens.expiry_date ? Math.max(1, Math.floor((tokens.expiry_date - Date.now()) / 1000)) : 3600,
        userName: channel?.snippet?.title || 'YouTube User',
        userChannelId: channel?.id || ''
      });
    } catch (err) {
      console.error('exchangeYouTubeCode failed', err);
      return res.status(500).json({ error: err.message || 'Code exchange failed' });
    }
  }
);

exports.youtubeAccessToken = onRequest(
  { secrets: [GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI] },
  async (req, res) => {
    addCors(res, req.headers.origin || '*');
    if (req.method === 'OPTIONS') return res.status(204).send('');
    if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

    try {
      const sessionId = req.get('X-FocusTube-Session') || req.body?.sessionId;
      const session = await getSessionDoc(sessionId);
      if (!session?.data?.refreshToken) {
        return res.status(401).json({ error: 'No stored refresh token for session' });
      }

      const oauth2Client = makeOAuth2Client();
      oauth2Client.setCredentials({ refresh_token: session.data.refreshToken });
      const { token, res: tokenRes } = await oauth2Client.getAccessToken();
      if (!token) {
        return res.status(401).json({ error: 'Could not refresh access token' });
      }

      let expiresIn = 3600;
      const expiryDate = oauth2Client.credentials.expiry_date;
      if (expiryDate) {
        expiresIn = Math.max(1, Math.floor((expiryDate - Date.now()) / 1000));
      } else if (tokenRes?.data?.expires_in) {
        expiresIn = tokenRes.data.expires_in;
      }

      await session.ref.set({
        updatedAt: admin.firestore.FieldValue.serverTimestamp()
      }, { merge: true });

      return res.json({
        ok: true,
        accessToken: token,
        expiresIn,
        userName: session.data.channelTitle || 'YouTube User',
        userChannelId: session.data.channelId || ''
      });
    } catch (err) {
      console.error('youtubeAccessToken failed', err);
      return res.status(500).json({ error: err.message || 'Refresh failed' });
    }
  }
);

exports.revokeYouTubeSession = onRequest(
  { secrets: [GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI] },
  async (req, res) => {
    addCors(res, req.headers.origin || '*');
    if (req.method === 'OPTIONS') return res.status(204).send('');
    if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

    try {
      const sessionId = req.get('X-FocusTube-Session') || req.body?.sessionId;
      const session = await getSessionDoc(sessionId);
      if (session?.data?.refreshToken) {
        const oauth2Client = makeOAuth2Client();
        oauth2Client.setCredentials({ refresh_token: session.data.refreshToken });
        try {
          await oauth2Client.revokeCredentials();
        } catch (e) {
          console.warn('revokeCredentials warning', e.message || e);
        }
      }
      if (session?.ref) await session.ref.delete();
      return res.json({ ok: true });
    } catch (err) {
      console.error('revokeYouTubeSession failed', err);
      return res.status(500).json({ error: err.message || 'Revoke failed' });
    }
  }
);
