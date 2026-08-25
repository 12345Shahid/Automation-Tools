const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcodeTerminal = require('qrcode-terminal');
const qrcode = require('qrcode');
const express = require('express');
const { generateResponse } = require('./ai_engine');
const dotenv = require('dotenv');

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

let client;
let currentQR = '';
let isAuthenticated = false;

function getBrowserExecutablePath() {
    const fs = require('fs');
    const { execSync } = require('child_process');

    // Check and clean dead environment variables
    if (process.env.PUPPETEER_EXECUTABLE_PATH) {
        if (fs.existsSync(process.env.PUPPETEER_EXECUTABLE_PATH)) {
            return process.env.PUPPETEER_EXECUTABLE_PATH;
        } else {
            console.log(`⚠️ Configured PUPPETEER_EXECUTABLE_PATH (${process.env.PUPPETEER_EXECUTABLE_PATH}) does not exist on disk! Removing dead env var...`);
            delete process.env.PUPPETEER_EXECUTABLE_PATH;
        }
    }

    const binaryNames = ['chromium', 'chromium-browser', 'google-chrome-stable', 'google-chrome'];
    for (const name of binaryNames) {
        try {
            let foundPath = execSync(`which ${name} 2>/dev/null`).toString().trim();
            if (foundPath && fs.existsSync(foundPath)) return foundPath;
            
            foundPath = execSync(`find /nix/store /nix/var /root/.nix-profile /usr /bin /snap -name "${name}" -type f -perm /111 2>/dev/null | head -n 1`).toString().trim();
            if (foundPath && fs.existsSync(foundPath)) return foundPath;
        } catch (e) {}
    }

    const standardPaths = [
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/google-chrome',
        '/snap/bin/chromium'
    ];
    for (const p of standardPaths) {
        if (fs.existsSync(p)) return p;
    }

    // 4. If NO system browser exists anywhere on disk, download Chrome on the fly!
    console.log(`⚠️ No system browser found anywhere on disk! Downloading Chrome on-the-fly right now...`);
    try {
        delete process.env.PUPPETEER_SKIP_CHROMIUM_DOWNLOAD;
        execSync('npx puppeteer browsers install chrome', { stdio: 'inherit' });
        // Locate the freshly downloaded chrome binary
        const downloadedPath = execSync(`find ~/.cache /app/.cache /root/.cache /home/pptruser/.cache ./ -name "chrome" -type f -perm /111 2>/dev/null | head -n 1`).toString().trim();
        if (downloadedPath && fs.existsSync(downloadedPath)) {
            console.log(`✅ Successfully downloaded Chrome on-the-fly to: ${downloadedPath}`);
            return downloadedPath;
        }
    } catch (e) {
        console.error(`❌ On-the-fly Chrome download encountered an error: ${e.message}`);
    }

    return undefined;
}

function initializeBot() {
    console.log('🚀 Initializing WhatsApp AI Agent...');

    const detectedBrowser = getBrowserExecutablePath();
    if (detectedBrowser) {
        console.log(`🌐 Using verified system browser binary at: ${detectedBrowser}`);
    } else {
        console.log(`🌐 Letting Puppeteer use its bundled internal browser...`);
    }

    client = new Client({
        authStrategy: new LocalAuth({ clientId: "commercial-ai-agent" }),
        puppeteer: {
            executablePath: detectedBrowser,
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-extensions', '--disable-gpu']
        }
    });

    client.on('qr', (qr) => {
        console.log('\n📱 Scan this QR code with your new commercial WhatsApp number:');
        qrcodeTerminal.generate(qr, { small: true });
        // Save QR code to display on the web dashboard
        qrcode.toDataURL(qr, (err, url) => {
            if (!err) {
                currentQR = url;
            }
        });
    });

    client.on('ready', () => {
        console.log('✅ WhatsApp AI Agent is connected and ready!');
        isAuthenticated = true;
        currentQR = '';
    });

    client.on('authenticated', () => {
        console.log('🔐 Authenticated successfully.');
        isAuthenticated = true;
        currentQR = '';
    });

    client.on('auth_failure', msg => {
        console.error('❌ Authentication failure:', msg);
        isAuthenticated = false;
    });

    client.on('disconnected', (reason) => {
        console.log(`🔌 Client was logged out or disconnected. Reason: ${reason}`);
        console.log('🔄 Attempting to restart in 5 seconds...');
        isAuthenticated = false;
        setTimeout(() => {
            client.initialize();
        }, 5000);
    });

    client.on('message', async (msg) => {
        try {
            // Ignore messages sent by the bot itself or status broadcasts
            if (msg.from === 'status@broadcast' || msg.id.fromMe) return;

            const contact = await msg.getContact();
            // Ignore group messages
            if (contact.isGroup) return;

            const userNumber = msg.from;
            const text = msg.body;

            console.log(`\n📥 Received message from ${contact.number || userNumber}: ${text}`);

            // Generate AI Response
            const aiResponse = await generateResponse(userNumber, text);
            
            console.log(`📤 AI Replying: ${aiResponse}`);

            // Send reply
            await msg.reply(aiResponse);

        } catch (error) {
            console.error('❌ Error handling message:', error);
        }
    });

    client.initialize();
}

// ---------------------------------------------------------
// EXPRESS WEB SERVER (For Railway QR Code Display)
// ---------------------------------------------------------
app.get('/', (req, res) => {
    if (isAuthenticated) {
        return res.send(`
            <html>
                <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1 style="color: green;">✅ WhatsApp AI Agent is Authenticated and Running!</h1>
                    <p>The bot is currently listening for inbound messages.</p>
                </body>
            </html>
        `);
    }

    if (currentQR) {
        return res.send(`
            <html>
                <head>
                    <meta http-equiv="refresh" content="5">
                </head>
                <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                    <h1>📱 Link Your Device</h1>
                    <p>Scan this QR code with your new commercial WhatsApp app to log in.</p>
                    <img src="${currentQR}" alt="QR Code" style="width: 300px; height: 300px;" />
                    <p style="color: gray; font-size: 14px;">This page refreshes automatically every 5 seconds.</p>
                </body>
            </html>
        `);
    }

    res.send(`
        <html>
            <head><meta http-equiv="refresh" content="3"></head>
            <body style="font-family: sans-serif; text-align: center; padding: 50px;">
                <h1>⏳ Generating QR Code...</h1>
                <p>Please wait a moment while the browser boots up. This page will refresh automatically.</p>
            </body>
        </html>
    `);
});

app.listen(PORT, () => {
    console.log(`\n🌐 Web Server running on port ${PORT}`);
    console.log(`👉 Open http://localhost:${PORT} in your browser to scan the QR code!`);
    
    // Start the WhatsApp Client alongside the web server
    initializeBot();
});
