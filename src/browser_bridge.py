import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Optional
from rich.console import Console

from browser_use import Browser, BrowserProfile

console = Console()

DEFAULT_CHROME_PORT = int(os.getenv("CHROME_DEBUG_PORT", "9222"))
MAC_CHROME_BIN = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

def is_chrome_debugging_port_open(port: int = DEFAULT_CHROME_PORT) -> bool:
    """Check if Chrome is already running with remote debugging open on the specified port."""
    url = f"http://127.0.0.1:{port}/json/version"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BrowserBridge"})
        with urllib.request.urlopen(req, timeout=1.5) as response:
            return response.status == 200
    except Exception:
        return False

def launch_local_chrome(port: int = DEFAULT_CHROME_PORT, profile_dir: Optional[str] = None) -> subprocess.Popen:
    """
    Launch Google Chrome on macOS with remote debugging enabled.
    This lets you use your personal session (already logged into LinkedIn, Google, etc.).
    """
    if is_chrome_debugging_port_open(port):
        console.print(f"[green]✓ Chrome is already running with remote debugging on port {port}.[/green]")
        return None

    if not Path(MAC_CHROME_BIN).exists():
        raise FileNotFoundError(f"Chrome binary not found at {MAC_CHROME_BIN}")

    # Use a dedicated profile or user-specified profile directory to avoid conflict with existing Chrome locks
    user_data = profile_dir or str(Path.home() / "Library/Application Support/Google/Chrome-AgentProfile")
    Path(user_data).mkdir(parents=True, exist_ok=True)

    cmd = [
        MAC_CHROME_BIN,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data}",
        "--no-first-run",
        "--no-default-browser-check"
    ]
    console.print(f"[cyan]Launching Chrome with remote debugging on port {port}...[/cyan]")
    process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return process

def get_browser(connect_existing_chrome: bool = True, port: int = DEFAULT_CHROME_PORT, headless: bool = False) -> Browser:
    """
    Returns a configured Browser instance.
    If connect_existing_chrome is True and port 9222 is active, connects via CDP.
    Otherwise, starts a managed browser session.
    """
    if connect_existing_chrome and is_chrome_debugging_port_open(port):
        cdp_url = f"http://127.0.0.1:{port}"
        console.print(f"[bold green]Connected to existing Chrome session at {cdp_url}[/bold green]")
        return Browser(cdp_url=cdp_url)
    
    if connect_existing_chrome and not is_chrome_debugging_port_open(port):
        console.print(
            f"[yellow]Notice: Chrome remote debugging port {port} is not running. "
            f"Falling back to managed browser instance (headless={headless}). "
            f"Run 'python cli.py launch-chrome' to use your existing Chrome login session.[/yellow]"
        )

    profile = BrowserProfile(headless=headless)
    return Browser(browser_profile=profile)
