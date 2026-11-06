#!/usr/bin/env python3
"""
Automation Tools Unified Suite Launcher
Starts services and interactive tools from a single entry point.
"""

import sys
import subprocess
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

console = Console()

def print_banner():
    console.print(Panel(
        "[bold cyan]🤖 AUTOMATION TOOLS SUITE[/bold cyan]\n"
        "[dim]Production-Grade Browser & Outreach Automation Systems[/dim]\n\n"
        " [bold white]1.[/bold white] [bold green]Start Bridge Server & Web Dashboards[/bold green] (Port 8000)\n"
        " [bold white]2.[/bold white] [bold yellow]Launch Email Outreach Agent (CLI)[/bold yellow]\n"
        " [bold white]3.[/bold white] [bold magenta]Start Conversational Email Chat Copilot[/bold magenta]\n"
        " [bold white]4.[/bold white] [bold blue]Search Jobs Across LinkedIn / Indeed / Glassdoor[/bold blue]\n"
        " [bold white]5.[/bold white] [bold cyan]Test Gmail SMTP & IMAP Connections[/bold cyan]\n"
        " [bold white]0.[/bold white] [dim]Exit[/dim]",
        border_style="cyan"
    ))

def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ("--server", "-s"):
            subprocess.run([sys.executable, "-m", "uvicorn", "server:app", "--port", "8000", "--reload"])
            return
        elif arg in ("--chat", "-c"):
            subprocess.run([sys.executable, "email_agent.py", "--chat"])
            return
        elif arg in ("--email", "-e"):
            subprocess.run([sys.executable, "email_agent.py", "--dry-run"])
            return

    while True:
        print_banner()
        choice = Prompt.ask("[bold cyan]Select an option[/bold cyan]", choices=["1", "2", "3", "4", "5", "0"], default="1")

        if choice == "1":
            console.print("\n[green]Starting FastAPI Bridge Server on http://127.0.0.1:8000 ...[/green]")
            subprocess.run([sys.executable, "-m", "uvicorn", "server:app", "--port", "8000", "--reload"])
            break
        elif choice == "2":
            subprocess.run([sys.executable, "email_agent.py", "--dry-run"])
            break
        elif choice == "3":
            subprocess.run([sys.executable, "email_agent.py", "--chat"])
            break
        elif choice == "4":
            query = Prompt.ask("[bold yellow]Enter job title to search[/bold yellow]", default="Software Engineer")
            subprocess.run([sys.executable, "cli.py", "search", query])
            break
        elif choice == "5":
            subprocess.run([sys.executable, "email_agent.py", "--test-smtp"])
            break
        elif choice == "0":
            console.print("[dim]Goodbye![/dim]")
            break

if __name__ == "__main__":
    main()
