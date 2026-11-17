const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcodeTerminal = require('qrcode-terminal');
const qrcode = require('qrcode');
const express = require('express');
const dotenv = require('dotenv');
const path = require('path');

dotenv.config({ path: path.join(__dirname, '../.env') });

const app = express();
const PORT = process.env.WHATSAPP_PORT || 3001;

const LINES = [
    { id: 'line_1', name: 'Sarah Line 1 (+8801746654426)', phone: '+8801746654426', enabled: true },
    { id: 'line_2', name: 'Line 2 (Pending Activation)', phone: '+19453260478', enabled: false },
    { id: 'line_3', name: 'Line 3 (Pending Activation)', phone: '+19453260334', enabled: false }
];

const sessions = {};

function initLine(line) {
    if (line.enabled === false) {
        sessions[line.id] = {
            config: line,
            client: null,
            status: 'standby',
            qrUrl: '',
            authenticated: false
        };
        console.log(`⏸️ [${line.name}] In standby mode. Line 1 is primary.`);
        return;
    }

    console.log(`🚀 Initializing WhatsApp Session for ${line.name} (${line.phone})...`);

    const chromePath = process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/google-chrome';
    const client = new Client({
        authStrategy: new LocalAuth({ clientId: `omnicall_${line.id}` }),
        puppeteer: {
            executablePath: chromePath,
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-extensions', '--disable-gpu']
        }
    });

    sessions[line.id] = {
        config: line,
        client: client,
        status: 'initializing',
        qrUrl: '',
        authenticated: false
    };

    client.on('qr', (qr) => {
        console.log(`\n📱 QR Code for ${line.name} (${line.phone}):`);
        qrcodeTerminal.generate(qr, { small: true });
        qrcode.toDataURL(qr, (err, url) => {
            if (!err) sessions[line.id].qrUrl = url;
            sessions[line.id].status = 'waiting_for_qr';
        });
    });

    client.on('authenticated', () => {
        console.log(`🔐 [${line.name}] Authenticated successfully!`);
        sessions[line.id].authenticated = true;
        sessions[line.id].status = 'connected';
        sessions[line.id].qrUrl = '';
    });

    client.on('ready', () => {
        console.log(`✅ [${line.name}] WhatsApp line is READY for voice calling and text outreach!`);
        sessions[line.id].status = 'ready';
    });

    client.on('disconnected', (reason) => {
        console.log(`🔌 [${line.name}] Disconnected (${reason}). Reconnecting in 5s...`);
        sessions[line.id].status = 'disconnected';
        sessions[line.id].authenticated = false;
        setTimeout(() => client.initialize(), 5000);
    });

    // Inbound text message handler
    client.on('message', async (msg) => {
        if (msg.from === 'status@broadcast' || msg.id.fromMe) return;
        const sender = msg.from;
        const text = msg.body;
        console.log(`📥 [${line.name}] Inbound text from ${sender}: ${text}`);
    });

    try {
        client.initialize();
    } catch (e) {
        console.error(`Error booting client for ${line.id}:`, e.message);
    }
}

// Web Pairing Dashboard
app.get('/', (req, res) => {
    let cardsHtml = '';

    LINES.forEach(line => {
        const s = sessions[line.id] || { status: 'idle', qrUrl: '', authenticated: false };
        let statusBadge = '';
        let qrSection = '';

        if (line.enabled === false) {
            statusBadge = '<span style="color:#9ca3af; font-weight:600;">⏸️ STANDBY (PENDING)</span>';
            qrSection = '<div style="padding:40px 20px; background:#f3f4f6; border-radius:12px; color:#6b7280; font-size:13px; line-height:1.5;">Line 1 (+8801746654426) is the active outreach line.<br>This slot activates when needed.</div>';
        } else if (s.authenticated) {
            statusBadge = '<span style="color:#10b981; font-weight:bold;">🟢 CONNECTED & READY</span>';
            qrSection = '<div style="padding:40px; background:#f0fdf4; border-radius:12px; color:#15803d; font-weight:600;">✅ Active Outreach Line<br><span style="font-size:13px; font-weight:normal; color:#166534;">Listening & Ready for Calling/Messaging</span></div>';
        } else if (s.qrUrl) {
            statusBadge = '<span style="color:#f59e0b; font-weight:bold;">🟡 SCAN QR TO LINK</span>';
            qrSection = `<img src="${s.qrUrl}" style="width:220px; height:220px; border:1px solid #e5e7eb; border-radius:8px;" /><br><small style="color:#6b7280; display:block; margin-top:10px;">WhatsApp > Settings / 3 Dots > Linked Devices > Link a Device</small>`;
        } else {
            statusBadge = '<span style="color:#6b7280;">⚪ INITIALIZING...</span>';
            qrSection = '<div style="padding:40px; color:#9ca3af;">Generating QR code...</div>';
        }

        cardsHtml += `
            <div style="flex:1; min-width:280px; max-width:340px; border:1px solid #e5e7eb; border-radius:16px; padding:24px; text-align:center; box-shadow:0 4px 6px -1px rgba(0,0,0,0.05); background:#ffffff;">
                <h3 style="margin:0 0 6px 0; font-size:18px; color:#111827;">${line.name}</h3>
                <div style="font-size:14px; color:#6b7280; margin-bottom:12px;">${line.phone}</div>
                <div style="margin-bottom:18px;">${statusBadge}</div>
                ${qrSection}
            </div>
        `;
    });

    res.send(`
        <!DOCTYPE html>
        <html>
        <head>
            <title>OmniCall AI: Multi-Line WhatsApp Pairing Portal</title>
            <meta http-equiv="refresh" content="6">
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f9fafb; margin:0; padding:40px 20px; }
            </style>
        </head>
        <body>
            <div style="max-width:1100px; margin:0 auto;">
                <div style="text-align:center; margin-bottom:36px;">
                    <h1 style="color:#111827; margin-bottom:8px;">🎙️ OmniCall: 3-Line WhatsApp Calling Portal</h1>
                    <p style="color:#4b5563; font-size:15px; margin:0;">Pair your 3 SignalWire US numbers here. Once paired, the autonomous calling agent rotates across all 3 lines.</p>
                </div>
                <div style="display:flex; gap:24px; justify-content:center; flex-wrap:wrap;">
                    ${cardsHtml}
                </div>
                <div style="text-align:center; margin-top:40px; font-size:13px; color:#9ca3af;">
                    Auto-refreshes every 6 seconds • Powered by OmniCall AI & Supabase
                </div>
            </div>
        </body>
        </html>
    `);
});

// Status API
app.get('/api/status', (req, res) => {
    const statusObj = {};
    LINES.forEach(l => {
        const s = sessions[l.id];
        statusObj[l.id] = {
            name: l.name,
            phone: l.phone,
            enabled: l.enabled !== false,
            authenticated: s ? s.authenticated : false,
            status: s ? s.status : 'offline'
        };
    });
    res.json(statusObj);
});

// Outbound Call / Text API for Python caller
app.use(express.json());
app.post('/api/send-text', async (req, res) => {
    const { lineId, to, text } = req.body;
    const session = sessions[lineId || 'line_1'];
    if (!session || !session.client || !session.authenticated) {
        return res.status(400).json({ ok: false, error: 'Line not connected' });
    }
    try {
        const jid = to.replace(/[^0-9]/g, '') + '@c.us';
        await session.client.sendMessage(jid, text);
        return res.json({ ok: true, status: 'sent' });
    } catch (e) {
        return res.status(500).json({ ok: false, error: e.message });
    }
});

app.post('/api/call', async (req, res) => {
    const { lineId, to } = req.body;
    const session = sessions[lineId || 'line_1'];
    if (!session || !session.client || !session.authenticated) {
        return res.status(400).json({ ok: false, error: 'Line not connected' });
    }
    try {
        const cleanPhone = to.replace(/[^0-9]/g, '');
        let callLink = null;
        try {
            callLink = await session.client.createCallLink({ callType: 'voice' });
        } catch (e) {}

        return res.json({
            ok: true,
            status: 'initiated',
            target: cleanPhone,
            callLink: callLink
        });
    } catch (e) {
        return res.status(500).json({ ok: false, error: e.message });
    }
});

app.listen(PORT, () => {
    console.log(`\n======================================================`);
    console.log(`🌐 Multi-Line WhatsApp Manager running on port ${PORT}`);
    console.log(`👉 Open http://localhost:${PORT} to scan QR codes for all 3 lines`);
    console.log(`======================================================\n`);
    
    // Auto-init all 3 lines
    LINES.forEach(initLine);
});
