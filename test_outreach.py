#!/usr/bin/env python3
"""
Test Calling & Outreach Agent (test_outreach.py)
Allows testing the Sarah persona outbound calling and WhatsApp outreach flow
against any specific phone number.

Usage:
    python3 test_outreach.py --to +8801746654426 --name "Hasan" --company "Hasan Contracting"
"""
import sys
import argparse
import logging
from dotenv import load_dotenv
from whatsapp_voice_agent import WhatsAppVoiceAgent

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def main():
    parser = argparse.ArgumentParser(description="Test OmniCall WhatsApp Calling & Outreach Agent")
    parser.add_argument("--to", type=str, default="+8801746654426", help="Destination phone number (E.164)")
    parser.add_argument("--name", type=str, default="Hasan", help="Contact name")
    parser.add_argument("--company", type=str, default="Hasan Contracting", help="Company name")
    args = parser.parse_args()

    agent = WhatsAppVoiceAgent()
    print("=" * 60)
    print("🎙️ OMNICALL AI: TESTING OUTBOUND OUTREACH AGENT")
    print("=" * 60)
    print(f"Target Number:  {args.to}")
    print(f"Contact Name:   {args.name}")
    print(f"Company Name:   {args.company}")
    print("=" * 60)

    import time
    test_lead = {
        "id": f"test_{int(time.time())}",
        "phone_number": args.to,
        "company_name": args.company,
        "contact_name": args.name,
        "outcome": "pending"
    }

    result = agent.execute_call_cycle(test_lead, simulate_voice=True)
    print("\n" + "=" * 60)
    print("📋 TEST EXECUTION RESULT:")
    print("=" * 60)
    for k, v in result.items():
        print(f"  {k}: {v}")
    print("=" * 60)
    print("✅ Telemetry and transcript persisted to Supabase.")

if __name__ == "__main__":
    main()
