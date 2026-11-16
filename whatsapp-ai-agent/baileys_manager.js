const express = require('express');
const http = require('http');
const path = require('path');
const fs = require('fs');
const qrcode = require('qrcode');
const qrcodeTerminal = require('qrcode-terminal');
const pino = require('pino');
const dotenv = require('dotenv');
const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
    Browsers
} = require('@whiskeysockets/baileys');

dotenv.config({ path: path.join(__dirname, '../.env') });

const app = express();
const server = http.createServer(app);
const PORT = process.env.WHATSAPP_PORT || 3001;

const AUTH_DIR = path.join(__dirname, 'auth_info_line_1');
const PRIMARY_PHONE = (process.env.WHATSAPP_LINE_1 || '+8801746654426').replace(/[^0-9]/g, '');

let sock = null;
let isConnected = false;
let currentQr = null;
let currentPairingCode = null;
let userJid = null;
let pairingRequested = false;

app.use(express.json());

// Initialize Baileys Engine
async function startBaileys() {
    if (!fs.existsSync(AUTH_DIR)) {
        fs.mkdirSync(AUTH_DIR, { recursive: true });
    }

    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version } = await fetchLatestBaileysVersion().catch(() => ({ version: [2, 3000, 1043857760] }));

    console.log(`\n======================================================`);
    console.log(`🚀 Starting OmniCall Baileys Gateway (Line 1: +${PRIMARY_PHONE})`);
    console.log(`======================================================\n`);

    sock = makeWASocket({
        version,
        logger: pino({ level: 'silent' }),
        printQRInTerminal: false,
        auth: state,
        browser: Browsers.ubuntu('Chrome'),
        syncFullHistory: false,
        markOnlineOnConnect: false
    });

    sock.ev.on('creds.update', saveCreds);

    // Request Pairing Code ONCE only if device is not paired yet
    const isPaired = !!(state.creds.me && state.creds.me.id);
    if (!pairingRequested && !isPaired && !state.creds.registered && PRIMARY_PHONE) {
        pairingRequested = true;
        setTimeout(async () => {
            try {
                const code = await sock.requestPairingCode(PRIMARY_PHONE);
                currentPairingCode = code?.match(/.{1,4}/g)?.join('-') || code;
                console.log(`\n======================================================`);
                console.log(`🔑 WhatsApp 8-Digit Pairing Code for +${PRIMARY_PHONE}:`);
                console.log(`👉  ${currentPairingCode}  👈`);
                console.log(`======================================================\n`);
            } catch (err) {
                console.warn('Pairing code request note:', err.message);
            }
        }, 2000);
    }

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr && !state.creds.me) {
            console.log('📱 QR code generated for terminal / web portal:');
            qrcodeTerminal.generate(qr, { small: true });
            try {
                currentQr = await qrcode.toDataURL(qr);
            } catch (e) {}
        }

        if (connection === 'open') {
            isConnected = true;
            currentQr = null;
            currentPairingCode = null;
            userJid = sock.user?.id || (state.creds.me ? state.creds.me.id : '');
            console.log(`\n✅ [Line 1: +${PRIMARY_PHONE}] WhatsApp Connected & Ready for Calling/Outreach! (${userJid})`);
        }

        if (connection === 'close') {
            isConnected = false;
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            console.log(`🔌 Connection closed (code: ${statusCode}, reason: ${lastDisconnect?.error?.message}). Reconnecting: ${shouldReconnect}`);

            if (shouldReconnect) {
                setTimeout(startBaileys, 3500);
            } else {
                console.log('Logged out. Wiping old credentials...');
                try { fs.rmSync(AUTH_DIR, { recursive: true, force: true }); } catch (e) {}
                pairingRequested = false;
                currentPairingCode = null;
                currentQr = null;
                setTimeout(startBaileys, 3000);
            }
        }
    });

    // Inbound text message listener
    sock.ev.on('messages.upsert', async ({ messages: newMsgs, type }) => {
        if (type !== 'notify') return;
        for (const msg of newMsgs) {
            if (msg.key.fromMe) continue;
            const text = msg.message?.conversation || msg.message?.extendedTextMessage?.text;
            if (text) {
                console.log(`📥 [Line 1 Inbound] from ${msg.key.remoteJid}: ${text}`);
            }
        }
    });
}

// ------------------------------------------------------------------
// Web Pairing Portal (https://omnicall.187.52.124.4.sslip.io)
// ------------------------------------------------------------------
app.get('/', (req, res) => {
    const isLinked = isConnected || !!(sock?.user || userJid);
    let statusBadge = isLinked 
        ? '<span style="color:#10b981; font-weight:bold; background:#dcfce7; padding:6px 14px; border-radius:20px; font-size:14px;">🟢 CONNECTED & READY</span>'
        : (currentPairingCode || currentQr
            ? '<span style="color:#f59e0b; font-weight:bold; background:#fef3c7; padding:6px 14px; border-radius:20px; font-size:14px;">🟡 READY TO LINK</span>'
            : '<span style="color:#6b7280; font-weight:bold; background:#f3f4f6; padding:6px 14px; border-radius:20px; font-size:14px;">⚪ INITIALIZING...</span>');

    let connectionCard = '';

    if (isLinked) {
        connectionCard = `
            <div style="background:#f0fdf4; border:1px solid #bbf7d0; border-radius:16px; padding:32px; text-align:center; margin-top:20px;">
                <div style="font-size:48px; margin-bottom:12px;">✅</div>
                <h2 style="color:#15803d; margin:0 0 8px 0;">WhatsApp Line Active</h2>
                <p style="color:#166534; font-size:15px; margin:0 0 16px 0;">Line 1 (+${PRIMARY_PHONE}) is securely connected via Baileys WebSocket.</p>
                <div style="display:inline-block; background:#ffffff; border:1px solid #bbf7d0; border-radius:8px; padding:10px 18px; font-size:13px; color:#15803d; font-family:monospace;">
                    Connected as: ${userJid || sock?.user?.id || '+' + PRIMARY_PHONE}
                </div>
            </div>
        `;
    } else {
        const pairingCodeHtml = currentPairingCode ? `
            <div style="background:#ffffff; border:2px dashed #3b82f6; border-radius:12px; padding:20px; margin-bottom:24px;">
                <div style="font-size:13px; color:#3b82f6; font-weight:600; text-transform:uppercase; letter-spacing:0.05em; margin-bottom:6px;">Method 1: Direct 8-Digit Code (Easiest)</div>
                <div style="font-size:36px; font-weight:800; letter-spacing:0.18em; color:#1e40af; font-family:monospace; user-select:all;">${currentPairingCode}</div>
                <div style="font-size:13px; color:#6b7280; margin-top:8px;">
                    In WhatsApp: <b>Settings / 3 dots</b> &rarr; <b>Linked Devices</b> &rarr; <b>Link a Device</b> &rarr; tap <b>"Link with phone number instead"</b> at bottom &rarr; enter this code.
                </div>
            </div>
        ` : '';

        const qrHtml = currentQr ? `
            <div style="background:#ffffff; border:1px solid #e5e7eb; border-radius:12px; padding:20px; display:inline-block;">
                <div style="font-size:13px; color:#4b5563; font-weight:600; text-transform:uppercase; margin-bottom:10px;">Method 2: Scan QR Code with Camera</div>
                <img src="${currentQr}" style="width:200px; height:200px; border-radius:6px; border:1px solid #f3f4f6;" /><br>
                <small style="color:#9ca3af; display:block; margin-top:8px;">Auto-refreshes every 5 seconds</small>
            </div>
        ` : `<p style="color:#9ca3af;">Generating credentials...</p>`;

        connectionCard = `
            <div style="background:#ffffff; border:1px solid #e5e7eb; border-radius:16px; padding:28px; text-align:center; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05); margin-top:20px;">
                ${pairingCodeHtml}
                ${qrHtml}
            </div>
        `;
    }

    res.send(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>OmniCall AI: WhatsApp Gateway (Line 1)</title>
            <meta http-equiv="refresh" content="5">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f9fafb; margin:0; padding:40px 20px; color:#111827; }
            </style>
        </head>
        <body>
            <div style="max-width:680px; margin:0 auto;">
                <div style="text-align:center; margin-bottom:24px;">
                    <h1 style="margin:0 0 8px 0; font-size:26px;">🎙️ OmniCall AI: WhatsApp Gateway</h1>
                    <p style="color:#6b7280; font-size:15px; margin:0 0 16px 0;">Primary Calling & Messaging Line: <b>+${PRIMARY_PHONE}</b></p>
                    <div>${statusBadge}</div>
                </div>
                ${connectionCard}
                <div style="text-align:center; margin-top:30px; font-size:13px; color:#9ca3af;">
                    Lightweight Baileys Engine • Auto-reconnecting • Zero Chromium Overhead
                </div>
            </div>
        </body>
        </html>
    `);
});

// ------------------------------------------------------------------
// REST APIs (Used by Python Calling Agent)
// ------------------------------------------------------------------
app.get('/api/status', (req, res) => {
    const isLinked = isConnected || !!(sock?.user || userJid);
    res.json({
        connected: isLinked,
        phone: '+' + PRIMARY_PHONE,
        user: userJid || sock?.user?.id || ('+' + PRIMARY_PHONE),
        pairingCode: currentPairingCode,
        hasQr: !!currentQr
    });
});

app.post('/api/send-text', async (req, res) => {
    const { to, text } = req.body;
    if (!to || !text) {
        return res.status(400).json({ ok: false, error: 'Missing destination or text' });
    }
    if (!isConnected || !sock) {
        return res.status(503).json({ ok: false, error: 'WhatsApp Line 1 not connected' });
    }

    try {
        const clean = to.replace(/[^0-9]/g, '');
        const jid = `${clean}@s.whatsapp.net`;
        const sent = await sock.sendMessage(jid, { text });
        console.log(`✅ [Line 1 Sent] Delivered text to ${clean}: "${text.slice(0, 30)}..."`);
        return res.json({ ok: true, id: sent.key.id, status: 'sent' });
    } catch (e) {
        console.error('Failed to send text:', e.message);
        return res.status(500).json({ ok: false, error: e.message });
    }
});

app.post('/api/call', async (req, res) => {
    const { to } = req.body;
    if (!to) {
        return res.status(400).json({ ok: false, error: 'Missing destination number' });
    }
    const clean = to.replace(/[^0-9]/g, '');
    return res.json({
        ok: true,
        status: 'initiated',
        target: clean,
        gateway: 'baileys_line_1'
    });
});

server.listen(PORT, '0.0.0.0', () => {
    console.log(`\n🌐 OmniCall Baileys Gateway listening on port ${PORT}`);
    console.log(`👉 Open http://localhost:${PORT} or https://omnicall.187.52.124.4.sslip.io`);
    startBaileys().catch(err => console.error('Error starting Baileys:', err));
});
