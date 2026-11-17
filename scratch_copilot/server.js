const express = require('express');
const http = require('http');
const { Server } = require('socket.io');
const cors = require('cors');
const fs = require('fs');
const path = require('path');
const qrcode = require('qrcode');
const pino = require('pino');
const {
    default: makeWASocket,
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
    Browsers
} = require('@whiskeysockets/baileys');

const app = express();
const server = http.createServer(app);
const io = new Server(server, { cors: { origin: '*' } });

const PORT = process.env.PORT || 5050;
const DATA_DIR = __dirname;
const CONFIG_FILE = path.join(DATA_DIR, 'config.json');
const MESSAGES_FILE = path.join(DATA_DIR, 'messages.json');
const AUTH_DIR = path.join(DATA_DIR, 'auth_info_baileys');

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Default Config
let config = {
    pin: '1234',
    targetJid: '141055919972366@lid',
    decoyProfile: {
        name: 'Nilima',
        phone: '+880 1712-394812',
        about: '',
        avatar: '/avatar.jpg',
        subtext: 'online'
    },
    defaultMode: 'decoy'
};

if (fs.existsSync(CONFIG_FILE)) {
    try {
        config = { ...config, ...JSON.parse(fs.readFileSync(CONFIG_FILE, 'utf-8')) };
    } catch (e) {
        console.error('Error loading config:', e);
    }
}

// Always ensure phone is the fake decoy number
if (!config.decoyProfile.phone || config.decoyProfile.phone.includes('1844')) {
    config.decoyProfile.phone = '+880 1712-394812';
}
if (!config.decoyProfile.name) {
    config.decoyProfile.name = 'Nilima';
}

function saveConfig() {
    fs.writeFileSync(CONFIG_FILE, JSON.stringify(config, null, 2));
}

// Messages Store
let messages = [];
if (fs.existsSync(MESSAGES_FILE)) {
    try {
        messages = JSON.parse(fs.readFileSync(MESSAGES_FILE, 'utf-8'));
    } catch (e) {
        messages = [];
    }
}

function saveMessages() {
    if (messages.length > 1000) messages = messages.slice(-1000);
    fs.writeFileSync(MESSAGES_FILE, JSON.stringify(messages, null, 2));
}

let sock = null;
let currentQr = null;
let isConnected = false;
let userJid = null;

// Track active web clients so VPS only shows online when user is active in web app
const activeWebClients = new Set();
let isUserOnline = false;

async function syncWhatsAppPresence() {
    if (!sock || !isConnected) return;
    const shouldBeOnline = activeWebClients.size > 0;
    if (shouldBeOnline !== isUserOnline) {
        isUserOnline = shouldBeOnline;
        try {
            await sock.sendPresenceUpdate(isUserOnline ? 'available' : 'unavailable');
            console.log('[Presence] WhatsApp user presence set to: ' + (isUserOnline ? 'AVAILABLE (online)' : 'UNAVAILABLE (offline)'));
        } catch (err) {
            console.error('[Presence] Error updating presence:', err.message);
        }
    }
}

const contactPresence = {};

async function subscribeTargetPresence() {
    if (!sock || !isConnected) return;
    try {
        if (config.targetJid) {
            await sock.presenceSubscribe(config.targetJid);
        }
        await sock.presenceSubscribe('8801844334732@s.whatsapp.net');
        console.log('[Presence] Active presence subscription sent for target');
    } catch (err) {
        console.error('[Presence] Error subscribing to presence:', err.message);
    }
}

function isTargetJid(jid) {
    if (!jid) return false;
    const clean = jid.split('@')[0].split(':')[0];
    const targetClean = config.targetJid ? config.targetJid.split('@')[0].split(':')[0] : '141055919972366';
    return jid === config.targetJid ||
           clean === targetClean ||
           clean === '141055919972366' ||
           clean === '8801844334732';
}

function formatLastSeen(timestampMs) {
    if (!timestampMs || isNaN(timestampMs)) return '';
    const d = new Date(timestampMs);
    let hours = d.getHours();
    const mins = String(d.getMinutes()).padStart(2, '0');
    const ampm = hours >= 12 ? 'pm' : 'am';
    hours = hours % 12 || 12;

    const today = new Date();
    const isToday = today.toDateString() === d.toDateString();
    if (isToday) {
        return 'last seen today at ' + hours + ':' + mins + ' ' + ampm;
    }
    const yesterday = new Date();
    yesterday.setDate(yesterday.getDate() - 1);
    if (yesterday.toDateString() === d.toDateString()) {
        return 'last seen yesterday at ' + hours + ':' + mins + ' ' + ampm;
    }
    return 'last seen ' + d.getDate() + '/' + (d.getMonth() + 1) + ' at ' + hours + ':' + mins + ' ' + ampm;
}

function getLastSeenStatus(targetJid) {
    const targetLid = '141055919972366@lid';
    const targetPhone = '8801844334732@s.whatsapp.net';
    const p = (targetJid && contactPresence[targetJid]) ||
              (config.targetJid && contactPresence[config.targetJid]) ||
              contactPresence[targetLid] ||
              contactPresence[targetPhone];

    if (p) {
        if (p.lastKnownPresence === 'composing') return 'typing...';
        if (p.lastKnownPresence === 'recording') return 'recording audio...';
        if (p.lastKnownPresence === 'available') return 'online';
        if (p.lastSeen) return formatLastSeen(p.lastSeen * 1000);
    }

    // Fallback: check incoming messages from target
    const incoming = messages.filter(m => (isTargetJid(m.jid) || (targetJid && m.jid === targetJid)) && !m.fromMe);
    if (incoming.length > 0) {
        const lastTime = incoming[incoming.length - 1].timestamp;
        return formatLastSeen(lastTime);
    }
    return '';
}

// Socket.IO for client connection and presence
io.on('connection', (socket) => {
    socket.on('client_presence', async (data) => {
        const isActive = (typeof data === 'boolean') ? data : (data && data.active === true);
        if (isActive) {
            activeWebClients.add(socket.id);
            await subscribeTargetPresence();
        } else {
            activeWebClients.delete(socket.id);
        }
        await syncWhatsAppPresence();
    });

    socket.on('disconnect', async () => {
        activeWebClients.delete(socket.id);
        await syncWhatsAppPresence();
    });
});

async function startBaileys() {
    const { state, saveCreds } = await useMultiFileAuthState(AUTH_DIR);
    const { version, isLatest } = await fetchLatestBaileysVersion();
    console.log(`Starting WhatsApp with Baileys v${version.join('.')}`);

    sock = makeWASocket({
        version,
        logger: pino({ level: 'silent' }),
        printQRInTerminal: false,
        auth: state,
        browser: Browsers.macOS('Desktop'),
        syncFullHistory: false,
        markOnlineOnConnect: false // CRITICAL: do not automatically mark online
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        if (qr) {
            console.log('New WhatsApp QR Code generated');
            try {
                currentQr = await qrcode.toDataURL(qr);
                io.emit('qr', currentQr);
            } catch (err) {
                console.error('QR conversion error:', err);
            }
        }

        if (connection === 'open') {
            console.log('WhatsApp connection opened successfully!');
            isConnected = true;
            currentQr = null;
            userJid = sock.user?.id || '';
            
            // Mark unavailable (offline) by default unless active web clients exist
            try {
                if (activeWebClients.size > 0) {
                    await sock.sendPresenceUpdate('available');
                    isUserOnline = true;
                } else {
                    await sock.sendPresenceUpdate('unavailable');
                    isUserOnline = false;
                }
            } catch (err) {
                console.error('Failed to set initial presence:', err.message);
            }

            setTimeout(async () => {
                await subscribeTargetPresence();
            }, 1500);

            io.emit('status', { connected: true, user: sock.user, targetJid: config.targetJid });
        }

        if (connection === 'close') {
            isConnected = false;
            const statusCode = lastDisconnect?.error?.output?.statusCode;
            const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
            console.log(`Connection closed: ${statusCode}, shouldReconnect: ${shouldReconnect}`);

            io.emit('status', { connected: false, loggedOut: !shouldReconnect });

            if (shouldReconnect) {
                setTimeout(startBaileys, 3000);
            } else {
                console.log('Logged out. Clearing auth files to allow fresh scan...');
                try {
                    fs.rmSync(AUTH_DIR, { recursive: true, force: true });
                } catch (e) {}
                setTimeout(startBaileys, 2000);
            }
        }
    });

    // Handle incoming messages
    sock.ev.on('messages.upsert', async ({ messages: newMsgs, type }) => {
        for (const msg of newMsgs) {
            if (!msg.message) continue;
            const jid = msg.key.remoteJid;
            if (jid === 'status@broadcast') continue;

            // Deduplicate if already saved
            if (messages.some(m => m.id === msg.key.id)) continue;

            const text = msg.message.conversation ||
                         msg.message.extendedTextMessage?.text ||
                         msg.message.imageMessage?.caption ||
                         msg.message.videoMessage?.caption ||
                         (msg.message.imageMessage ? '[Image]' : '') ||
                         (msg.message.audioMessage ? '[Voice Note]' : '');

            if (!text && !msg.message.imageMessage && !msg.message.audioMessage) continue;

            const msgObj = {
                id: msg.key.id,
                jid: jid,
                fromMe: msg.key.fromMe,
                text: text || '[Media]',
                timestamp: msg.messageTimestamp ? Number(msg.messageTimestamp) * 1000 : Date.now(),
                sender: msg.pushName || jid.split('@')[0],
                status: msg.status || (msg.key.fromMe ? 2 : 4)
            };

            messages.push(msgObj);
            saveMessages();

            // Emit to frontend
            io.emit('new_message', msgObj);
        }
    });

    // Handle message status updates (ticks: delivery and read receipts)
    sock.ev.on('messages.update', async (updates) => {
        let changed = false;
        for (const { key, update } of updates) {
            if (!update.status) continue;
            const msg = messages.find(m => m.id === key.id);
            if (msg) {
                // Strictly monotonic: 1 (pending) -> 2 (server ack) -> 3 (delivered) -> 4 (read)
                const newStatus = Number(update.status);
                const currentStatus = Number(msg.status || 0);
                if (newStatus > currentStatus) {
                    msg.status = newStatus;
                    changed = true;
                    io.emit('message_status_update', { id: key.id, status: newStatus });
                }
            }
        }
        if (changed) {
            saveMessages();
        }
    });

    // Presence update from contacts (typing & live online/last seen status)
    sock.ev.on('presence.update', ({ id, presences }) => {
        if (!presences) return;
        for (const [participant, presence] of Object.entries(presences)) {
            const jid = id || participant;
            const isTarget = isTargetJid(jid) || isTargetJid(participant);

            contactPresence[jid] = {
                ...contactPresence[jid],
                ...presence
            };
            if (participant && participant !== jid) {
                contactPresence[participant] = {
                    ...contactPresence[participant],
                    ...presence
                };
            }
            if (isTarget) {
                const targetLid = '141055919972366@lid';
                const targetPhone = '8801844334732@s.whatsapp.net';
                contactPresence[targetLid] = { ...contactPresence[targetLid], ...presence };
                contactPresence[targetPhone] = { ...contactPresence[targetPhone], ...presence };
                if (config.targetJid) {
                    contactPresence[config.targetJid] = { ...contactPresence[config.targetJid], ...presence };
                }
            }

            const isTyping = presence.lastKnownPresence === 'composing';
            io.emit('typing', { jid, isTyping });
            const statusStr = getLastSeenStatus(jid);
            io.emit('status_update', { jid, status: statusStr });
            if (isTarget && config.targetJid && jid !== config.targetJid) {
                io.emit('status_update', { jid: config.targetJid, status: statusStr });
            }
        }
    });
}

// REST API Endpoints
app.post('/api/auth', (req, res) => {
    const { pin } = req.body;
    if (pin === config.pin) {
        return res.json({ ok: true });
    }
    return res.status(401).json({ ok: false, error: 'Incorrect PIN' });
});

app.get('/api/status', (req, res) => {
    res.json({
        connected: isConnected,
        qr: currentQr,
        user: userJid,
        targetJid: config.targetJid,
        lastSeen: getLastSeenStatus(config.targetJid),
        decoyProfile: config.decoyProfile,
        defaultMode: config.defaultMode,
        isUserOnline
    });
});

app.get('/api/chats', (req, res) => {
    const chatMap = {};
    for (const m of messages) {
        if (!chatMap[m.jid]) {
            chatMap[m.jid] = {
                jid: m.jid,
                lastMessage: m.text,
                timestamp: m.timestamp,
                sender: m.sender || m.jid.split('@')[0]
            };
        } else if (m.timestamp > chatMap[m.jid].timestamp) {
            chatMap[m.jid].lastMessage = m.text;
            chatMap[m.jid].timestamp = m.timestamp;
        }
    }
    res.json(Object.values(chatMap).sort((a, b) => b.timestamp - a.timestamp));
});

app.get('/api/messages', (req, res) => {
    const jid = req.query.jid || config.targetJid;
    if (!jid) return res.json([]);
    const filtered = messages.filter(m => (isTargetJid(m.jid) || m.jid === jid));
    res.json(filtered.slice(-150));
});

app.post('/api/send', async (req, res) => {
    const { jid, text } = req.body;
    const destJid = jid || config.targetJid;
    if (!destJid || !text) {
        return res.status(400).json({ ok: false, error: 'Missing JID or text' });
    }
    if (!isConnected || !sock) {
        return res.status(503).json({ ok: false, error: 'WhatsApp not connected' });
    }

    try {
        const sent = await sock.sendMessage(destJid, { text });
        const msgObj = {
            id: sent.key.id,
            jid: destJid,
            fromMe: true,
            text: text,
            timestamp: Date.now(),
            sender: 'You',
            status: sent.status || 2 // SERVER_ACK (sent)
        };
        messages.push(msgObj);
        saveMessages();
        io.emit('new_message', msgObj);
        res.json({ ok: true, message: msgObj });
    } catch (err) {
        console.error('Failed to send message:', err);
        res.status(500).json({ ok: false, error: err.message });
    }
});

app.post('/api/config', (req, res) => {
    const { targetJid, decoyProfile, pin, defaultMode } = req.body;
    if (targetJid !== undefined) config.targetJid = targetJid.trim();
    if (decoyProfile !== undefined) config.decoyProfile = { ...config.decoyProfile, ...decoyProfile };
    if (pin !== undefined && pin.length >= 4) config.pin = pin;
    if (defaultMode !== undefined) config.defaultMode = defaultMode;
    saveConfig();
    io.emit('config_updated', config);
    res.json({ ok: true, config });
});

app.post('/api/logout', (req, res) => {
    if (sock) {
        try { sock.logout(); } catch (e) {}
    }
    try { fs.rmSync(AUTH_DIR, { recursive: true, force: true }); } catch (e) {}
    isConnected = false;
    currentQr = null;
    setTimeout(startBaileys, 1500);
    res.json({ ok: true, message: 'Logged out. Initializing new pairing...' });
});

server.listen(PORT, '0.0.0.0', () => {
    console.log(`Stealth Copilot server listening on port ${PORT}`);
    startBaileys().catch(err => console.error('Error starting Baileys:', err));
});
