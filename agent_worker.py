#!/usr/bin/env python3
"""
Decoupled Autonomous Background Worker Daemon (agent_worker.py)
Allows you or the Master Orchestrator to start a campaign in the background with a single command.
The worker runs completely independently (non-blocking) without holding the terminal or conversation.

Commands:
    ./.venv/bin/python agent_worker.py start [--industry "Roofers"] [--location "Dallas, TX"] [--count 10]
    ./.venv/bin/python agent_worker.py status
    ./.venv/bin/python agent_worker.py stop
"""

import os
import sys
import time
import json
import signal
import logging
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

PID_FILE = Path(__file__).parent / "agent_worker.pid"
LOG_FILE = Path(__file__).parent / "agent_worker.log"
CONFIG_FILE = Path(__file__).parent / "worker_config.json"

def get_running_pid():
    if not PID_FILE.exists():
        return None
    try:
        pid = int(PID_FILE.read_text().strip())
        # Check if process is still running
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        if PID_FILE.exists():
            PID_FILE.unlink()
        return None

def start_daemon(args):
    pid = get_running_pid()
    if pid:
        print(f"⚠️ Agent worker is already running in the background with PID {pid}!")
        print("Run `python agent_worker.py status` to monitor it.")
        return

    # Save campaign parameters
    config = {
        "industry": args.industry,
        "location": args.location,
        "count": args.count,
        "started_at": datetime.now().isoformat(),
        "status": "running"
    }
    CONFIG_FILE.write_text(json.dumps(config, indent=2))

    python_bin = sys.executable

    # Spawn background worker process detached
    cmd = [
        python_bin,
        str(Path(__file__).resolve()),
        "--run-worker"
    ]

    with open(LOG_FILE, "a") as log_out:
        log_out.write(f"\n\n======================================================\n")
        log_out.write(f"🚀 Launching Agent Worker Batch at {datetime.now().isoformat()}\n")
        log_out.write(f"Target: {args.count} leads in '{args.industry}' ({args.location})\n")
        log_out.write(f"======================================================\n")
        log_out.flush()

        proc = subprocess.Popen(
            cmd,
            stdout=log_out,
            stderr=log_out,
            stdin=subprocess.DEVNULL,
            start_new_session=True
        )

    PID_FILE.write_text(str(proc.pid))
    print(f"✅ Autonomous Agent Worker launched in background! (PID: {proc.pid})")
    print(f"📁 Log file: {LOG_FILE}")
    print(f"💡 You and Antigravity can now continue other work freely.")
    print(f"   Check progress anytime with: python agent_worker.py status")

def run_worker_loop():
    """Executed by the detached daemon process."""
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s - [WORKER %(process)d] - %(levelname)s - %(message)s"
    )

    logging.info("Autonomous Agent Worker started inside background process.")

    config = {}
    if CONFIG_FILE.exists():
        try:
            config = json.loads(CONFIG_FILE.read_text())
        except Exception:
            pass

    industry = config.get("industry", "Roofing contractors")
    location = config.get("location", "Dallas, TX")
    count = config.get("count", 10)

    try:
        # Step 1: Autonomous Scraping & Lead Discovery
        from pipeline_scraper import scrape_leads
        logging.info(f"Phase 1: Discovering leads for '{industry}' in '{location}'...")
        scraped = scrape_leads(industry=industry, location=location, count=count)
        logging.info(f"Phase 1 complete: {len(scraped)} leads verified and queued in Supabase.")

        # Step 2: Calling & Messaging Outreach Execution
        from whatsapp_voice_agent import WhatsAppVoiceAgent
        agent = WhatsAppVoiceAgent()
        
        logging.info("Phase 2: Fetching pending leads and starting multi-line calling cycle...")
        pending_leads = agent.fetch_pending_leads(limit=count)
        logging.info(f"Loaded {len(pending_leads)} pending leads for outreach.")

        successful = 0
        voicemails = 0
        unanswered = 0

        for idx, lead in enumerate(pending_leads, 1):
            logging.info(f"Processing lead [{idx}/{len(pending_leads)}]: {lead.get('company_name')} ({lead.get('phone_number')})")
            res = agent.execute_call_cycle(lead, simulate_voice=True)
            
            grp = res.get("group", "")
            if grp == "group1_humans":
                successful += 1
            elif grp == "group2_voicemails":
                voicemails += 1
            else:
                unanswered += 1

            # Natural inter-call delay (spam prevention & cooldown)
            delay = 12
            logging.info(f"Waiting {delay}s cooldown before next line dispatch...")
            time.sleep(delay)

        logging.info("======================================================")
        logging.info(f"🎉 Campaign Batch Completed Successfully!")
        logging.info(f"Summary: Total Processed: {len(pending_leads)} | Live Pickups: {successful} | Voicemails Cut: {voicemails} | Unanswered: {unanswered}")
        logging.info("======================================================")

        config["status"] = "completed"
        config["completed_at"] = datetime.now().isoformat()
        config["stats"] = {
            "processed": len(pending_leads),
            "live_pickups": successful,
            "voicemails_cut": voicemails,
            "unanswered": unanswered
        }
        CONFIG_FILE.write_text(json.dumps(config, indent=2))

    except Exception as e:
        logging.error(f"❌ Error in worker execution loop: {e}", exc_info=True)
        config["status"] = "failed"
        config["error"] = str(e)
        CONFIG_FILE.write_text(json.dumps(config, indent=2))

    finally:
        if PID_FILE.exists():
            PID_FILE.unlink()
        logging.info("Autonomous Agent Worker terminated cleanly.")

def show_status():
    pid = get_running_pid()
    print("==================================================")
    print("        Autonomous Voice Agent Worker Status      ")
    print("==================================================")
    if pid:
        print(f"  Status        : 🟢 RUNNING (PID: {pid})")
    else:
        print(f"  Status        : ⚪ IDLE / STOPPED")

    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text())
            print(f"  Target        : {cfg.get('industry')} in {cfg.get('location')}")
            print(f"  Target Count  : {cfg.get('count')} leads")
            print(f"  Started At    : {cfg.get('started_at')}")
            if cfg.get("status") == "completed":
                print(f"  Completed At  : {cfg.get('completed_at')}")
                print(f"  Last Stats    : {cfg.get('stats')}")
        except Exception:
            pass

    print("--------------------------------------------------")
    if LOG_FILE.exists():
        print("  Recent Log Output (last 8 lines):")
        lines = LOG_FILE.read_text().splitlines()[-8:]
        for line in lines:
            print("   ", line)
    print("==================================================")

def stop_daemon():
    pid = get_running_pid()
    if not pid:
        print("⚪ No agent worker process currently running.")
        return
    try:
        os.kill(pid, signal.SIGTERM)
        time.sleep(1)
        if get_running_pid():
            os.kill(pid, signal.SIGKILL)
        if PID_FILE.exists():
            PID_FILE.unlink()
        print(f"🛑 Stopped background agent worker (PID: {pid}).")
    except Exception as e:
        print(f"Error stopping worker: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Autonomous Voice Agent Worker Manager")
    parser.add_argument("action", choices=["start", "status", "stop"], nargs="?", default="status", help="Worker action")
    parser.add_argument("--industry", type=str, default="Roofing contractors", help="Target industry keyword")
    parser.add_argument("--location", type=str, default="Dallas, TX", help="Location (City, State/Country)")
    parser.add_argument("--count", type=int, default=10, help="Number of leads to process")
    parser.add_argument("--run-worker", action="store_true", help="Internal flag for detached daemon process")

    parsed_args = parser.parse_args()

    if parsed_args.run_worker:
        run_worker_loop()
    elif parsed_args.action == "start":
        start_daemon(parsed_args)
    elif parsed_args.action == "status":
        show_status()
    elif parsed_args.action == "stop":
        stop_daemon()
