# ⚡ Automation Tools Suite
### Production-Grade AI Browser Agents, Community Outreach & Autonomous Email Copilots

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Chrome MV3](https://img.shields.io/badge/Chrome_Extension-Manifest_V3-4285F4.svg?logo=google-chrome&logoColor=white)](https://developer.chrome.com/docs/extensions/mv3/intro/)
[![Gmail SMTP/IMAP](https://img.shields.io/badge/Protocol-SMTP%20%2F%20IMAP%20SSL-EA4335.svg?logo=gmail&logoColor=white)](https://support.google.com/mail/answer/7126229)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A unified monorepo of three production-ready automation engines designed for high-scale workflows, outbound lead generation, and job market acceleration. Built with Python, FastAPI, Chrome Extensions (Manifest V3), and modern AI/LLM integrations.

---

## 🏛️ System Architecture

```mermaid
flowchart TB
    subgraph UI_Layer ["🖥️ User Interfaces & Extensions"]
        EXT1["Chrome Job Co-Pilot (Side Panel)"]
        EXT2["Chrome Skool Assistant (Content Script & HUD)"]
        WEB["FastAPI Web Dashboard (/email-agent)"]
        CLI["Rich Terminal CLI (email_agent.py & main.py)"]
    end

    subgraph Backend_Layer ["⚡ Backend Bridge & Core Engine (FastAPI)"]
        SRV["FastAPI Server (server.py)"]
        DISCO["Job Discovery Engine (python-jobspy)"]
        MATCHER["DOM Field Matcher & LLM Engine"]
        READER["IMAP Email Reader & Search (email_reader.py)"]
        SENDER["SMTP TLS Dispatcher (email_sender.py)"]
        CHAT["Conversational Chat Engine (email_chat_engine.py)"]
        WRITER["AI Email Copywriter (email_writer.py)"]
    end

    subgraph Storage_Layer ["💾 Persistence & Safety Engine"]
        PROF["Candidate Profile (data/candidate_profile.json)"]
        HIST["Sent Email History (data/email_sent_history.json)"]
        RECIP["Recipients Leads (recipients.txt / csv)"]
    end

    subgraph External_Layer ["🌐 External Services & APIs"]
        BOARDS["Job Boards (LinkedIn, Indeed, Glassdoor)"]
        SKOOL["Skool Communities (Web App)"]
        GMAIL["Gmail (SMTP Port 587 / IMAP Port 993)"]
        LLMS["LLM Providers (OpenAI, Gemini, Claude, DeepSeek)"]
    end

    %% UI Connections
    EXT1 -->|REST API: Match & Resume| SRV
    EXT2 -->|Scrapes & Messages| SKOOL
    WEB -->|REST API: Preview, Send, Chat| SRV
    CLI -->|Direct Command Line| SENDER
    CLI -->|Terminal Chat| CHAT

    %% Backend Connections
    SRV --> DISCO
    SRV --> MATCHER
    SRV --> READER
    SRV --> SENDER
    SRV --> CHAT

    DISCO -->|Scrapes Aggregated Postings| BOARDS
    MATCHER -->|Prompt Reasoning| LLMS
    WRITER -->|Draft Generation| LLMS
    CHAT --> WRITER
    CHAT --> READER
    CHAT --> SENDER

    %% Storage Connections
    MATCHER --> PROF
    SENDER --> HIST
    READER --> GMAIL
    SENDER --> GMAIL
    CLI --> RECIP
```

---

## 📦 The 3 Automation Systems

### 1. 💼 AI Job Application Co-Pilot & Autofill Extension
A Chrome Side Panel extension (Manifest V3) that searches job aggregators and automatically autofills complex job application forms (LinkedIn Easy Apply, Greenhouse, Lever, Workday, and custom career portals).

* **Zero-Token Instant DOM Parsing**: Extracts form fields in milliseconds directly within Chrome JavaScript without paying for expensive vision models or screenshot processing.
* **Micro-Cost LLM Field Matching**: Maps detected inputs (text fields, radio groups, date pickers, dropdown selects) to your candidate profile for less than **\$0.0001 per application**.
* **Automated Resume Upload Simulation**: Automatically attaches your PDF resume from the local backend bridge.
* **Pause Before Submit**: Outlines all autofilled fields in green and pauses before the final submission button so you always remain in full control.
* **Instant Multi-Board Job Discovery**: Scrapes and aggregates LinkedIn, Indeed, and Glassdoor in under 3 seconds using `python-jobspy`.

---

### 2. 🎓 Skool Community Automated Outreach Assistant
A dedicated Chrome Extension designed for ethical, automated lead generation and member outreach inside Skool communities.

* **Smart Member Directory Scraper**: Automatically identifies member cards, profile links, names, and handles from community `/members` pages.
* **Admin Shield (Anti-Ban Protection)**: Detects and automatically skips Community Creators, Admins, Moderators, and Staff to safeguard your account against bans.
* **Nested Spintax Engine**: Supports syntax like `{Hey|Hi|Hello} {first_name}! {Hope you are well|Hope you're having a productive week}` ensuring every outgoing direct message has a unique text hash.
* **Human Typing Simulation & Randomized Jitter**: Simulates human keystrokes with randomized delay intervals (45–90s) between messages.
* **In-Page Floating HUD**: Real-time on-screen countdown timer, queue counter, and 1-click `[Pause]`, `[Resume]`, and `[Stop]` controls.

---

### 3. 📬 Autonomous Cold Email Outreach & Inbox Copilot
A conversational outbound email engine with Gmail SMTP TLS dispatch, IMAP SSL inbox reader, keyword search, and an interactive 3-in-1 Web Dashboard.

* **Conversational Chat Dispatching**: Chat in natural English (e.g. *"Email alex@acme.com and tell him I can build a website for \$1"*). The agent infers the company and contact name, generates a personalized pitch, and provides a 1-click dispatch card or direct auto-send.
* **Gmail IMAP SSL Inbox Reader**: Reads incoming emails, parses RFC 2047 headers, decodes multipart plain/HTML content, and generates executive summaries.
* **Smart Search Engine**: Query incoming mail by sender, subject, or message body text (e.g. *"Find emails from Google"*, *"Search emails about invoice"*).
* **Anti-Spam & Duplicate Shield**: Maintains persistent history in `data/email_sent_history.json` to guarantee you never email the same contact twice. Automatically introduces randomized pauses (8–15s) between batch dispatches.
* **Zero-Credit Fallback Architecture**: Automatically switches to dynamic, high-converting templates if LLM balance runs out, ensuring zero crashes or downtime.
* **3-in-1 Web Dashboard**: Hosted at `http://127.0.0.1:8000/email-agent` with tabs for AI Chat Copilot, Bulk Campaigns, and Live Inbox Explorer.

---

## 📂 Repository Structure

```
Automation-Tools/
├── .env.example                # Clean environment variables template
├── .gitignore                  # Security-first ignore rules (prevents credential leaks)
├── pyproject.toml              # Modern Python packaging configuration (uv/pip)
├── requirements.txt            # Traditional pip dependency manifest
├── main.py                     # Unified interactive CLI launcher
├── server.py                   # FastAPI bridge backend & REST endpoints
├── email_agent.py              # CLI runner for email campaigns & chat copilot
├── cli.py                      # CLI tool for job discovery & Chrome debugging
│
├── extension/                  # Chrome Extension 1: Job Co-Pilot
│   ├── manifest.json           # Manifest V3 configuration (sidePanel, storage)
│   ├── background.js           # Extension lifecycle & side panel worker
│   ├── content.js              # DOM scanner & synthetic event injector
│   ├── content.css             # In-page element highlight styling
│   ├── sidepanel/              # Side panel interface (Discovery, Apply, Profile)
│   └── test_job_form.html      # Local mock job form for offline testing
│
├── skool-agent/                # Chrome Extension 2: Skool Outreach Assistant
│   ├── manifest.json           # Manifest V3 configuration
│   ├── background.js           # Campaign state manager & deduplication store
│   ├── content.js              # Member list scraper, typing simulator & Floating HUD
│   ├── popup/                  # Extension popup controller & Spintax editor
│   └── test_skool_community.html # Local mock Skool community for offline testing
│
├── src/                        # Core Python Engine & Logic
│   ├── email_chat_engine.py    # Conversational intent parser & natural language router
│   ├── email_reader.py         # IMAP SSL client (inbox fetching, search, summaries)
│   ├── email_sender.py         # SMTP TLS client with multipart MIME & rate limiting
│   ├── email_writer.py         # AI outreach copywriter with zero-credit fallbacks
│   ├── discovery.py            # JobSpy multi-board job aggregator
│   ├── applier.py              # Background browser automation engine
│   ├── browser_bridge.py       # Chrome DevTools Protocol remote debugging bridge
│   └── config.py               # Multi-provider LLM factory & candidate profile loader
│
├── static/                     # Web Dashboard Assets
│   └── email_agent.html        # Single-Page Web Dashboard (Chat, Bulk, Inbox)
│
├── data/                       # Local Data & Templates
│   ├── candidate_profile.json  # Candidate details for job autofill
│   └── resumes/
│       └── sample_resume.pdf   # PDF resume for auto-upload
│
├── recipients.txt              # Text template for email leads
└── recipients.csv              # CSV template for structured leads with notes
```

---

## ⚡ Quick Start & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/12345Shahid/Automation-Tools.git
cd Automation-Tools
```

### 2. Set Up Virtual Environment & Dependencies

Using [`uv`](https://github.com/astral-sh/uv) (Recommended):
```bash
uv venv
source .venv/bin/activate
uv sync
```

Or using standard `pip`:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Copy the template and fill in your credentials:
```bash
cp .env.example .env
```
Key settings:
* **Gmail App Password**: Create a 16-character password at [Google App Passwords](https://myaccount.google.com/apppasswords) and set `SMTP_PASSWORD` & `SMTP_USER`.
* **LLM API Key**: Provide an `OPENAI_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, or `KIE_API_KEY`.

---

## 🚀 Usage Guide

### Unified Launcher
Run the interactive master menu:
```bash
python main.py
```

### 1. Running the FastAPI Bridge Server & Web Dashboard
```bash
python -m uvicorn server:app --port 8000 --reload
```
Open **[http://127.0.0.1:8000/email-agent](http://127.0.0.1:8000/email-agent)** for the Web Dashboard:
* **Tab 1: 💬 AI Chat Copilot** — Chat in natural English to compose and send emails.
* **Tab 2: 👥 Bulk Campaign** — Paste target leads and dispatch in batches with safe delays.
* **Tab 3: 📬 Inbox & Search** — Search incoming Gmail messages by sender, subject, or body text.

### 2. Loading the Chrome Extensions

#### Load Job Co-Pilot:
1. Open Google Chrome and navigate to `chrome://extensions`.
2. Toggle on **Developer mode** (top-right corner).
3. Click **Load unpacked** and select the [`extension/`](extension/) directory.
4. Click the extension icon on any job application tab (or press `Cmd+Shift+P`) to open the Side Panel.

#### Load Skool Outreach Assistant:
1. In `chrome://extensions`, click **Load unpacked** and select the [`skool-agent/`](skool-agent/) directory.
2. Open any Skool community `/members` page (or test locally at `http://127.0.0.1:8000/skool-test`).
3. Click the extension icon to set your message template with Spintax, then click **Start Outreach**.

### 3. CLI Commands for Email Automation
```bash
# Start conversational terminal chat
python email_agent.py --chat

# View recent inbox emails
python email_agent.py --check-inbox --limit 5

# Search emails by keyword or sender
python email_agent.py --search "google"

# Dry-run batch campaign (preview without sending)
python email_agent.py --dry-run

# Dispatch email campaign with spam prevention delays
python email_agent.py --send

# Send a single test email
python email_agent.py --to client@example.com --name "John" --send
```

### 4. CLI Commands for Job Search
```bash
# Search across LinkedIn, Indeed, and Glassdoor
python cli.py search "Full Stack Developer" --location "Remote" --country "usa" --limit 10
```

---

## 🛡️ Security, Privacy & Ethics

* **Zero Credential Exposure**: `.env` and personal run histories (`data/email_sent_history.json`) are strictly gitignored.
* **Standard RFC Headers**: Emails are sent with appropriate RFC 2047 encoding, unique Message-IDs, and multipart alternative formatting.
* **Rate-Limiting & Jitter**: All outreach tools implement randomized delays to simulate natural human behavior and comply with platform limits.
* **Admin Shields**: Automated safeguards skip community leaders, staff, and previously messaged contacts to maintain community trust.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## 👤 Author

**Shahid Hasan**
* GitHub: [@12345Shahid](https://github.com/12345Shahid)
* Email: [shahidhasanpollob@gmail.com](mailto:shahidhasanpollob@gmail.com)
