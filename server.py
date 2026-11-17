#!/usr/bin/env python3
"""
OmniCall Browser Calling Server (server.py)
Flask management API & web portal for the WhatsApp Web browser calling service.
Listens on port 3002.
"""

import os
import sys
import logging
from flask import Flask, request, jsonify, render_template_string
from browser_agent import WhatsAppBrowserCaller

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)
PORT = int(os.environ.get("BROWSER_CALLER_PORT", 3002))

# Initialize Browser Caller
caller = WhatsAppBrowserCaller()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>OmniCall AI: Conversational Voice Caller (Line 1)</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f3f4f6; margin: 0; padding: 40px 20px; color: #111827; }
        .card { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 16px; padding: 32px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 24px; }
        .badge { display: inline-block; padding: 6px 14px; border-radius: 9999px; font-weight: 700; font-size: 13px; letter-spacing: 0.04em; }
        .badge-green { background: #d1fae5; color: #065f46; border: 1px solid #a7f3d0; }
        .badge-amber { background: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
        .badge-blue { background: #dbeafe; color: #1e40af; border: 1px solid #bfdbfe; }
        .code-box { background: #eff6ff; border: 2px dashed #3b82f6; border-radius: 12px; padding: 24px; text-align: center; margin: 20px 0; }
        .code-text { font-size: 42px; font-weight: 800; font-family: monospace; letter-spacing: 0.2em; color: #1e40af; }
        .btn { background: #059669; color: #ffffff; border: none; padding: 12px 24px; border-radius: 8px; font-weight: 600; font-size: 15px; cursor: pointer; transition: background 0.2s; }
        .btn:hover { background: #047857; }
        .btn:disabled { background: #9ca3af; cursor: not-allowed; }
        .btn-blue { background: #2563eb; }
        .btn-blue:hover { background: #1d4ed8; }
        .btn-red { background: #dc2626; }
        .btn-red:hover { background: #b91c1c; }
        input[type="text"] { width: 100%; padding: 12px 16px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 16px; box-sizing: border-box; margin-bottom: 16px; }
        .transcript-box { background: #111827; color: #f9fafb; border-radius: 8px; padding: 16px; font-family: monospace; font-size: 13px; max-height: 280px; overflow-y: auto; line-height: 1.5; }
        .turn-user { color: #60a5fa; margin-bottom: 8px; }
        .turn-sarah { color: #34d399; margin-bottom: 8px; }
        .status-pill { font-weight: 600; padding: 4px 10px; border-radius: 6px; font-size: 12px; margin-left: 8px; }
    </style>
</head>
<body>
    <div style="max-width: 680px; margin: 0 auto;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="margin: 0 0 8px 0; font-size: 26px;">📞 OmniCall AI: Conversational Voice Caller</h1>
            <p style="color: #6b7280; margin: 0 0 16px 0;">Line 1 Companion Device: <b>+880 {{ caller.local_number }}</b></p>
            <div id="statusBadgeContainer">
                {% if caller.is_connected %}
                    <span class="badge badge-green">🟢 CONNECTED & READY TO CALL</span>
                {% else %}
                    <span class="badge badge-amber">🟡 PAIRING REQUIRED</span>
                {% endif %}
            </div>
        </div>

        <div id="callPanelCard" class="card" style="{% if not caller.is_connected %}display:none;{% endif %}">
            <h2 style="margin-top: 0; font-size: 18px;">🎙️ Outbound Voice Dialing Panel</h2>
            <p style="color: #4b5563; font-size: 14px; margin-bottom: 20px;">
                Chrome opens the recipient's chat and triggers the native WhatsApp Web <b>Voice Call</b> with hardware-level bidirectional audio.
            </p>

            <form id="callForm" onsubmit="handleCall(event)">
                <label style="display:block; font-weight:600; margin-bottom:6px; font-size:14px;">Recipient Phone Number (E.164):</label>
                <input type="text" id="targetPhone" name="to" value="+8801917427815" placeholder="+8801xxxxxxxxx" required />
                
                <div style="display:flex; gap:12px;">
                    <button type="submit" id="callBtn" class="btn" style="flex:1;">📞 Place WhatsApp Voice Call</button>
                    <button type="button" class="btn btn-red" onclick="handleHangup()">🛑 End Call</button>
                </div>
            </form>
            <div id="callResult" style="margin-top:16px; font-size:14px; font-weight:600;"></div>
        </div>

        <div id="transcriptCard" class="card" style="{% if not caller.is_connected %}display:none;{% endif %}">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <h2 style="margin: 0; font-size: 18px;">🗣️ Live In-Call Conversational Transcript</h2>
                <span id="callStateLabel" class="status-pill" style="background:#e5e7eb; color:#374151;">IDLE</span>
            </div>
            <div id="transcriptBox" class="transcript-box">
                <div style="color: #9ca3af;">(Waiting for active call to connect...)</div>
            </div>
        </div>

        <div id="pairingCard" class="card" style="{% if caller.is_connected %}display:none;{% endif %}">
            <h2 style="margin-top: 0; font-size: 18px;">📱 Link WhatsApp Web Companion Device</h2>
            <p style="color: #4b5563; font-size: 14px; line-height: 1.6;">
                On your phone (<b>+880 {{ caller.local_number }}</b>):<br>
                1. Open <b>WhatsApp</b> &rarr; tap <b>Settings</b> (or 3 dots).<br>
                2. Tap <b>Linked Devices</b> &rarr; tap <b>Link a Device</b>.<br>
                3. Scan the QR code below:
            </p>

            <div style="text-align: center; margin-top: 16px;">
                <img id="qrImage" src="/api/screenshot" style="max-width: 100%; border: 1px solid #e5e7eb; border-radius: 8px;" />
            </div>

            <div style="text-align: center; margin-top: 16px;">
                <button class="btn btn-blue" onclick="refreshQr()">🔄 Refresh QR Code</button>
            </div>
        </div>

        <div style="text-align: center; font-size: 13px; color: #9ca3af; margin-top: 24px;">
            Persistent Chrome Profile • Hardware PulseAudio WebRTC • Zero-Cost Telephony
        </div>
    </div>

    <script>
        let isPolling = true;

        async function updateStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                
                // Update badge
                const badgeBox = document.getElementById('statusBadgeContainer');
                const callPanel = document.getElementById('callPanelCard');
                const transcriptCard = document.getElementById('transcriptCard');
                const pairingCard = document.getElementById('pairingCard');
                const stateLabel = document.getElementById('callStateLabel');

                if (data.connected) {
                    badgeBox.innerHTML = '<span class="badge badge-green">🟢 CONNECTED & READY TO CALL</span>';
                    callPanel.style.display = 'block';
                    transcriptCard.style.display = 'block';
                    pairingCard.style.display = 'none';
                } else {
                    badgeBox.innerHTML = '<span class="badge badge-amber">🟡 PAIRING REQUIRED</span>';
                    callPanel.style.display = 'none';
                    transcriptCard.style.display = 'none';
                    pairingCard.style.display = 'block';
                }

                // Update call state pill
                if (data.call_state === 'connected') {
                    stateLabel.style.background = '#d1fae5';
                    stateLabel.style.color = '#065f46';
                    stateLabel.innerText = 'LIVE IN-CALL';
                } else if (data.call_state === 'ringing' || data.call_state === 'calling') {
                    stateLabel.style.background = '#dbeafe';
                    stateLabel.style.color = '#1e40af';
                    stateLabel.innerText = data.call_state.toUpperCase() + '...';
                } else {
                    stateLabel.style.background = '#e5e7eb';
                    stateLabel.style.color = '#374151';
                    stateLabel.innerText = 'IDLE';
                }

                // Update transcript
                const box = document.getElementById('transcriptBox');
                if (data.transcript && data.transcript.length > 0) {
                    let html = '';
                    data.transcript.forEach(t => {
                        if (t.role === 'assistant') {
                            html += '<div class="turn-sarah"><b>Sarah:</b> ' + escapeHtml(t.text) + '</div>';
                        } else {
                            html += '<div class="turn-user"><b>Caller:</b> ' + escapeHtml(t.text) + '</div>';
                        }
                    });
                    box.innerHTML = html;
                    box.scrollTop = box.scrollHeight;
                }
            } catch(e) {}
        }

        function escapeHtml(text) {
            const div = document.createElement('div');
            div.innerText = text;
            return div.innerHTML;
        }

        async function handleCall(e) {
            e.preventDefault();
            const phone = document.getElementById('targetPhone').value;
            const resEl = document.getElementById('callResult');
            const btn = document.getElementById('callBtn');
            btn.disabled = true;
            resEl.style.color = '#1e40af';
            resEl.innerText = '⏳ Opening chat and placing WhatsApp Voice Call to ' + phone + '...';
            try {
                const res = await fetch('/api/call', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({to: phone})
                });
                const data = await res.json();
                if (data.ok) {
                    resEl.style.color = '#065f46';
                    resEl.innerText = '✅ ' + data.message;
                } else {
                    resEl.style.color = '#b91c1c';
                    resEl.innerText = '❌ Error: ' + (data.error || 'Failed to place call');
                }
            } catch (err) {
                resEl.style.color = '#b91c1c';
                resEl.innerText = '❌ Request failed: ' + err.message;
            } finally {
                setTimeout(() => { btn.disabled = false; }, 3000);
            }
        }

        async function handleHangup() {
            const resEl = document.getElementById('callResult');
            try {
                await fetch('/api/hangup', {method: 'POST'});
                resEl.style.color = '#92400e';
                resEl.innerText = '🛑 Call hung up.';
            } catch(e) {}
        }

        async function refreshQr() {
            try {
                await fetch('/api/show-qr', {method: 'POST'});
                document.getElementById('qrImage').src = '/api/screenshot?t=' + Date.now();
            } catch(e) {}
        }

        // Poll dynamically every 2 seconds without full-page reloads
        setInterval(updateStatus, 2000);
        updateStatus();
    </script>
</body>
</html>
"""

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_TEMPLATE, caller=caller)

@app.route("/api/status", methods=["GET"])
def api_status():
    return jsonify({
        "connected": caller.is_connected,
        "phone": "+880" + caller.local_number,
        "pairing_code": caller.pairing_code,
        "call_state": caller.call_state,
        "active_target": caller.active_call_target,
        "transcript": caller.active_call_transcript
    })

@app.route("/api/show-qr", methods=["POST"])
def api_show_qr():
    ok = caller.show_qr_code()
    return jsonify({"ok": ok})

@app.route("/api/request-code", methods=["POST"])
def api_request_code():
    code = caller.request_pairing_code()
    return jsonify({"ok": bool(code), "code": code})

@app.route("/api/call", methods=["POST"])
def api_call():
    data = request.get_json(silent=True) or request.form
    target = data.get("to")
    if not target:
        return jsonify({"ok": False, "error": "Missing destination number 'to'"}), 400
    res = caller.make_voice_call(target)
    return jsonify(res)

@app.route("/api/screenshot", methods=["GET"])
def api_screenshot():
    from flask import send_file
    path = caller.take_screenshot()
    if path and os.path.exists(path):
        return send_file(path, mimetype="image/png")
    return jsonify({"ok": False, "error": "Failed to take screenshot"}), 500

@app.route("/api/hangup", methods=["POST"])
def api_hangup():
    res = caller.hangup()
    return jsonify(res)

if __name__ == "__main__":
    caller.start()
    app.run(host="0.0.0.0", port=PORT)
