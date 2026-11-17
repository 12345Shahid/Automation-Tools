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
    <meta http-equiv="refresh" content="4">
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
        .btn-blue { background: #2563eb; }
        .btn-blue:hover { background: #1d4ed8; }
        .btn-red { background: #dc2626; }
        .btn-red:hover { background: #b91c1c; }
        input[type="text"] { width: 100%; padding: 12px 16px; border: 1px solid #d1d5db; border-radius: 8px; font-size: 16px; box-sizing: border-box; margin-bottom: 16px; }
        .transcript-box { background: #111827; color: #f9fafb; border-radius: 8px; padding: 16px; font-family: monospace; font-size: 13px; max-height: 240px; overflow-y: auto; }
        .turn-user { color: #60a5fa; margin-bottom: 6px; }
        .turn-sarah { color: #34d399; margin-bottom: 6px; }
    </style>
</head>
<body>
    <div style="max-width: 680px; margin: 0 auto;">
        <div style="text-align: center; margin-bottom: 30px;">
            <h1 style="margin: 0 0 8px 0; font-size: 26px;">📞 OmniCall AI: Conversational Voice Caller</h1>
            <p style="color: #6b7280; margin: 0 0 16px 0;">Line 1 Companion Device: <b>+880 {{ caller.local_number }}</b></p>
            {% if caller.is_connected %}
                <span class="badge badge-green">🟢 CONNECTED & READY TO CALL</span>
            {% elif caller.call_state != 'idle' %}
                <span class="badge badge-blue">🔵 CALL IN PROGRESS: {{ caller.call_state.upper() }}</span>
            {% else %}
                <span class="badge badge-amber">🟡 PAIRING CODE REQUIRED</span>
            {% endif %}
        </div>

        {% if not caller.is_connected %}
        <div class="card">
            <h2 style="margin-top: 0; font-size: 18px;">📱 Link WhatsApp Web Companion Device</h2>
            <p style="color: #4b5563; font-size: 14px; line-height: 1.6;">
                On your phone (<b>+880 {{ caller.local_number }}</b>):<br>
                1. Open <b>WhatsApp</b> &rarr; tap <b>Settings</b> (or 3 dots).<br>
                2. Tap <b>Linked Devices</b> &rarr; tap <b>Link a Device</b>.<br>
                3. At the bottom, tap <b>"Link with phone number instead"</b>.<br>
                4. Enter the 8-digit code below:
            </p>

            <div class="code-box">
                <div style="font-size: 13px; color: #6b7280; text-transform: uppercase; margin-bottom: 8px; font-weight: 600;">Your 8-Digit Pairing Code:</div>
                <div class="code-text">{{ caller.pairing_code or 'GENERATING...' }}</div>
                <small style="color: #9ca3af; display: block; margin-top: 8px;">Auto-refreshes every 4 seconds</small>
            </div>

            <div style="text-align: center; margin-top: 16px;">
                <button class="btn btn-blue" onclick="requestCode()">🔄 Request New 8-Digit Code</button>
            </div>
            
            <div style="margin-top: 24px; text-align: center;">
                <p style="font-size: 13px; color: #6b7280;">Or scan QR code directly if preferred:</p>
                <img src="/api/screenshot?t={{ caller.call_start_time or 0 }}" style="max-width: 100%; border: 1px solid #e5e7eb; border-radius: 8px;" />
            </div>
        </div>
        {% else %}
        <div class="card">
            <h2 style="margin-top: 0; font-size: 18px;">🎙️ Outbound Voice Dialing Panel</h2>
            <p style="color: #4b5563; font-size: 14px; margin-bottom: 20px;">
                Chrome will navigate to the recipient's chat and click the native WhatsApp Web <b>Voice Call</b> button to connect live audio.
            </p>

            <form action="/api/call" method="POST" onsubmit="handleCall(event)">
                <label style="display:block; font-weight:600; margin-bottom:6px; font-size:14px;">Recipient Phone Number (E.164):</label>
                <input type="text" id="targetPhone" name="to" value="+8801917427815" placeholder="+8801xxxxxxxxx" required />
                
                <div style="display:flex; gap:12px;">
                    <button type="submit" class="btn" style="flex:1;">📞 Place WhatsApp Voice Call</button>
                    <button type="button" class="btn btn-red" onclick="handleHangup()">🛑 End Call</button>
                </div>
            </form>
            <div id="callResult" style="margin-top:16px; font-size:14px; font-weight:600;"></div>
        </div>

        <div class="card">
            <h2 style="margin-top: 0; font-size: 18px;">🗣️ Live In-Call Conversational Transcript</h2>
            <div class="transcript-box">
                {% if caller.active_call_transcript %}
                    {% for turn in caller.active_call_transcript %}
                        {% if turn.role == 'assistant' %}
                            <div class="turn-sarah"><b>Sarah:</b> {{ turn.text }}</div>
                        {% else %}
                            <div class="turn-user"><b>Caller:</b> {{ turn.text }}</div>
                        {% endif %}
                    {% endfor %}
                {% else %}
                    <div style="color: #9ca3af;">(Waiting for active call to connect...)</div>
                {% endif %}
            </div>
        </div>
        {% endif %}

        <div style="text-align: center; font-size: 13px; color: #9ca3af;">
            Persistent Chrome Profile • Real WebRTC Media Stream • Zero-Cost Telephony
        </div>
    </div>

    <script>
        async function requestCode() {
            try {
                await fetch('/api/request-code', {method: 'POST'});
                location.reload();
            } catch(e) {
                alert('Request failed');
            }
        }

        async function handleCall(e) {
            e.preventDefault();
            const phone = document.getElementById('targetPhone').value;
            const resEl = document.getElementById('callResult');
            resEl.style.color = '#1e40af';
            resEl.innerText = 'Calling ' + phone + ' via Chrome...';
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

@app.route("/api/request-code", methods=["POST"])
def api_request_code():
    code = caller.request_pairing_code()
    return jsonify({"ok": bool(code), "code": code})

@app.route("/api/show-qr", methods=["POST"])
def api_show_qr():
    ok = caller.show_qr_code()
    return jsonify({"ok": ok})

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
