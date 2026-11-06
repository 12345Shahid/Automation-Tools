#!/usr/bin/env python3
"""
Autonomous Email Outreach & Management Agent
Supports AI campaign dispatch, interactive chat copilot, and Gmail inbox reading/search.
"""

import argparse
import csv
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm, Prompt
from rich.markdown import Markdown

from src.email_sender import EmailSender
from src.email_writer import generate_outreach_email
from src.email_reader import EmailReader
from src.email_chat_engine import EmailChatEngine

console = Console()

def load_recipients_from_file(file_path: Path) -> List[Dict[str, str]]:
    """Loads recipients from a .txt or .csv file."""
    if not file_path.exists():
        console.print(f"[bold red]❌ File not found:[/bold red] {file_path}")
        return []

    recipients = []
    
    if file_path.suffix.lower() == ".csv":
        with open(file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                email = row.get("email", "").strip()
                if email and not email.startswith("#"):
                    recipients.append({
                        "email": email,
                        "name": row.get("name", "").strip(),
                        "company": row.get("company", "").strip(),
                        "notes": row.get("notes", "").strip()
                    })
    else:
        # .txt format
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split(",")]
                email = parts[0]
                name = parts[1] if len(parts) > 1 else ""
                company = parts[2] if len(parts) > 2 else ""
                notes = parts[3] if len(parts) > 3 else ""
                recipients.append({
                    "email": email,
                    "name": name,
                    "company": company,
                    "notes": notes
                })

    return recipients

def test_smtp_cmd(sender: EmailSender):
    """Test SMTP connection and print results."""
    console.print("[cyan]Testing Gmail SMTP connection...[/cyan]")
    ok, msg = sender.test_connection()
    if ok:
        console.print(Panel(
            f"[bold green]✅ SMTP Authentication Successful![/bold green]\n\n"
            f"[white]Host:[/white] {sender.host}:{sender.port}\n"
            f"[white]Sender Account:[/white] {sender.user}\n"
            f"[white]Display Name:[/white] {sender.sender_name}\n"
            f"[dim]{msg}[/dim]",
            title="Gmail SMTP Status",
            border_style="green"
        ))
    else:
        console.print(Panel(
            f"[bold red]❌ SMTP Authentication Failed![/bold red]\n\n"
            f"[yellow]{msg}[/yellow]\n\n"
            f"Please verify your credentials in [bold].env[/bold] file.",
            title="Gmail SMTP Error",
            border_style="red"
        ))

def run_dry_run(recipients: List[Dict[str, str]], sender: EmailSender):
    """Generate and preview emails without sending them."""
    console.print(Panel(
        f"[bold cyan]🔍 DRY RUN PREVIEW MODE[/bold cyan]\n"
        f"Generating and previewing AI emails for [bold yellow]{len(recipients)}[/bold yellow] recipient(s). No emails will be sent.",
        border_style="cyan"
    ))

    table = Table(title="Generated Outreach Emails", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Recipient", style="bold green", width=26)
    table.add_column("Status", width=12)
    table.add_column("Subject", style="bold yellow", width=34)
    table.add_column("Preview Snippet", style="white", width=40)

    for i, lead in enumerate(recipients, 1):
        email = lead["email"]
        already_sent = sender.is_already_sent(email)
        status_text = "[red]Already Sent[/red]" if already_sent else "[green]Ready[/green]"

        draft = generate_outreach_email(
            email=email,
            name=lead.get("name"),
            company=lead.get("company"),
            custom_notes=lead.get("notes")
        )
        
        snippet = draft["body_text"].replace("\n", " ")[:90] + "..."
        table.add_row(str(i), email, status_text, draft["subject"], snippet)

    console.print(table)
    
    if recipients:
        first_lead = recipients[0]
        first_draft = generate_outreach_email(
            email=first_lead["email"],
            name=first_lead.get("name"),
            company=first_lead.get("company"),
            custom_notes=first_lead.get("notes")
        )
        console.print("\n[bold]Sample Full Email Preview (Lead #1):[/bold]")
        console.print(Panel(
            f"[bold yellow]To:[/bold yellow] {first_lead['email']}\n"
            f"[bold yellow]Subject:[/bold yellow] {first_draft['subject']}\n"
            f"[dim]----------------------------------------[/dim]\n"
            f"{first_draft['body_text']}",
            title=f"Draft for {first_lead['email']}",
            border_style="blue"
        ))

def run_send_campaign(
    recipients: List[Dict[str, str]],
    sender: EmailSender,
    force: bool = False,
    delay_min: int = 8,
    delay_max: int = 15
):
    """Send out cold emails to the recipients list with human delays."""
    console.print(Panel(
        f"[bold green]🚀 OUTREACH DISPATCH CAMPAIGN[/bold green]\n"
        f"Sender: [bold]{sender.sender_name}[/bold] <{sender.sender_email}>\n"
        f"Total Leads: [bold yellow]{len(recipients)}[/bold yellow]\n"
        f"Delay Between Sends: [bold]{delay_min} - {delay_max} seconds[/bold] (spam prevention)\n"
        f"Skip Previous Sends: [bold]{'Disabled (--force)' if force else 'Enabled'}[/bold]",
        border_style="green"
    ))

    if len(recipients) > 1:
        if not Confirm.ask(f"[bold yellow]Do you want to proceed and send to {len(recipients)} leads?[/bold yellow]"):
            console.print("[dim]Cancelled by user.[/dim]")
            return

    sent_count = 0
    skipped_count = 0
    failed_count = 0

    for i, lead in enumerate(recipients, 1):
        email = lead["email"]
        console.print(f"\n[cyan][{i}/{len(recipients)}][/cyan] Processing [bold]{email}[/bold]...")

        if not force and sender.is_already_sent(email):
            console.print(f"  [yellow]⚠️ Skipped:[/yellow] Already contacted previously.")
            skipped_count += 1
            continue

        draft = generate_outreach_email(
            email=email,
            name=lead.get("name"),
            company=lead.get("company"),
            custom_notes=lead.get("notes")
        )

        console.print(f"  [dim]Subject:[/dim] {draft['subject']}")
        result = sender.send_email(
            to_email=email,
            subject=draft["subject"],
            body_text=draft["body_text"],
            body_html=draft["body_html"],
            force=force
        )

        if result.get("success"):
            console.print(f"  [bold green]✅ Sent successfully![/bold green]")
            sent_count += 1
        else:
            console.print(f"  [bold red]❌ Failed to send:[/bold red] {result.get('error')}")
            failed_count += 1

        if i < len(recipients):
            import random
            delay = random.uniform(delay_min, delay_max)
            console.print(f"  [dim]Waiting {delay:.1f}s before next send...[/dim]")
            time.sleep(delay)

    console.print(Panel(
        f"[bold]Campaign Summary:[/bold]\n"
        f"[green]Sent:[/green] {sent_count}\n"
        f"[yellow]Skipped (Duplicates):[/yellow] {skipped_count}\n"
        f"[red]Failed:[/red] {failed_count}",
        title="Finished",
        border_style="green" if failed_count == 0 else "yellow"
    ))

def run_check_inbox_cmd(limit: int = 5):
    """Fetch and display recent inbox emails in a rich table."""
    reader = EmailReader()
    console.print(f"[cyan]Connecting to Gmail IMAP and fetching last {limit} emails...[/cyan]")
    emails = reader.fetch_recent_emails(limit=limit)
    if not emails:
        console.print("[yellow]No emails found in INBOX.[/yellow]")
        return

    table = Table(title=f"Recent Gmail Inbox ({len(emails)} emails)", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("From", style="bold green", width=28)
    table.add_column("Subject", style="bold yellow", width=34)
    table.add_column("Date", style="dim", width=20)
    table.add_column("Snippet", style="white", width=42)

    for i, em in enumerate(emails, 1):
        date_short = em.get("date", "").split(" +")[0].split(" -")[0]
        table.add_row(
            str(i),
            em.get("from_email") or em.get("from", ""),
            em.get("subject", "(No Subject)"),
            date_short,
            em.get("snippet", "")[:90] + "..."
        )

    console.print(table)

def run_search_emails_cmd(query: str, limit: int = 6):
    """Search inbox emails and display results in a rich table."""
    reader = EmailReader()
    console.print(f"[cyan]Searching inbox for: [bold]{query}[/bold]...[/cyan]")
    results = reader.search_emails(query=query, limit=limit)
    if not results:
        console.print(f"[yellow]No emails found matching '{query}'.[/yellow]")
        return

    table = Table(title=f"Search Results for '{query}' ({len(results)} matches)", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("From", style="bold green", width=28)
    table.add_column("Subject", style="bold yellow", width=34)
    table.add_column("Snippet", style="white", width=45)

    for i, em in enumerate(results, 1):
        table.add_row(
            str(i),
            em.get("from_email") or em.get("from", ""),
            em.get("subject", "(No Subject)"),
            em.get("snippet", "")[:100] + "..."
        )

    console.print(table)

def run_interactive_chat():
    """Start an interactive conversational assistant loop in the terminal."""
    engine = EmailChatEngine()
    console.print(Panel(
        "[bold cyan]💬 CONVERSATIONAL EMAIL ASSISTANT[/bold cyan]\n\n"
        "You can chat in plain English! Try asking:\n"
        " • [bold yellow]Email alex@acme.com and tell him I can build a website for $1[/bold yellow]\n"
        " • [bold yellow]Check my last 5 emails[/bold yellow]\n"
        " • [bold yellow]Find emails from google[/bold yellow]\n"
        " • [bold yellow]Search emails about invoice[/bold yellow]\n"
        " • [bold yellow]Summarize my recent emails[/bold yellow]\n\n"
        "Type [bold red]exit[/bold red] or [bold red]quit[/bold red] to return to the shell.",
        title="Email Copilot Ready",
        border_style="cyan"
    ))

    while True:
        try:
            user_input = console.input("\n[bold cyan]You > [/bold cyan]").strip()
            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q", "bye"):
                console.print("[dim]Goodbye![/dim]")
                break

            console.print("[dim]Thinking & checking...[/dim]")
            res = engine.process_chat(user_input)
            
            # Print response
            console.print("\n[bold green]Agent >[/bold green]")
            console.print(Markdown(res["response"]))

            # If draft was created, prompt if they want to dispatch immediately
            if res.get("action") == "draft_created":
                draft_data = res.get("data", {})
                recipient = draft_data.get("to")
                if Confirm.ask(f"\n[bold yellow]Do you want to send this email to {recipient} now?[/bold yellow]"):
                    send_res = engine.sender.send_email(
                        to_email=recipient,
                        subject=draft_data["subject"],
                        body_text=draft_data["body_text"],
                        body_html=draft_data.get("body_html"),
                        force=True
                    )
                    if send_res.get("success"):
                        console.print(f"[bold green]✅ Email sent successfully to {recipient}![/bold green]")
                    else:
                        console.print(f"[bold red]❌ Failed to send:[/bold red] {send_res.get('error')}")

        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Session ended.[/dim]")
            break

def main():
    parser = argparse.ArgumentParser(description="Autonomous Cold Email Outreach Agent & Copilot")
    parser.add_argument("--chat", action="store_true", help="Start interactive conversational email chat")
    parser.add_argument("--check-inbox", action="store_true", help="Check and display latest emails in inbox")
    parser.add_argument("--search", type=str, help="Search emails by sender, subject, or keyword")
    parser.add_argument("--send", action="store_true", help="Send outreach emails (default is dry-run)")
    parser.add_argument("--dry-run", action="store_true", help="Preview generated emails without sending")
    parser.add_argument("--to", type=str, help="Target a single email address directly")
    parser.add_argument("--name", type=str, help="Recipient name (optional, used with --to)")
    parser.add_argument("--company", type=str, help="Recipient company (optional, used with --to)")
    parser.add_argument("--file", type=str, default="recipients.txt", help="Path to recipients list (.txt or .csv)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of emails to process")
    parser.add_argument("--force", action="store_true", help="Send even if email was already contacted")
    parser.add_argument("--test-smtp", action="store_true", help="Test SMTP connection and exit")
    parser.add_argument("--delay-min", type=int, default=8, help="Minimum seconds between emails")
    parser.add_argument("--delay-max", type=int, default=15, help="Maximum seconds between emails")

    args = parser.parse_args()
    sender = EmailSender()

    if args.test_smtp:
        test_smtp_cmd(sender)
        return

    if args.chat:
        run_interactive_chat()
        return

    if args.check_inbox:
        limit = args.limit if args.limit > 0 else 5
        run_check_inbox_cmd(limit=limit)
        return

    if args.search:
        run_search_emails_cmd(query=args.search, limit=args.limit if args.limit > 0 else 6)
        return

    # Single recipient target
    if args.to:
        recipients = [{
            "email": args.to.strip(),
            "name": args.name or "",
            "company": args.company or "",
            "notes": ""
        }]
    else:
        file_path = Path(args.file)
        if not file_path.is_absolute():
            file_path = Path(__file__).resolve().parent / file_path
        recipients = load_recipients_from_file(file_path)

    if not recipients:
        console.print("[yellow]No recipients found. Please add emails to recipients.txt or specify --to <email>[/yellow]")
        return

    if args.limit > 0:
        recipients = recipients[:args.limit]

    if args.send:
        run_send_campaign(
            recipients=recipients,
            sender=sender,
            force=args.force,
            delay_min=args.delay_min,
            delay_max=args.delay_max
        )
    else:
        run_dry_run(recipients, sender)
        console.print("\n[bold cyan]💡 Tip:[/bold cyan] When you're ready to dispatch real emails, run:\n   [bold green]uv run python email_agent.py --send[/bold green]\n   or start the chat assistant:\n   [bold green]uv run python email_agent.py --chat[/bold green]\n")

if __name__ == "__main__":
    main()
