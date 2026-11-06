import asyncio
import json
import typer
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.panel import Panel

from src.config import get_candidate_profile, BASE_DIR
from src.browser_bridge import launch_local_chrome, is_chrome_debugging_port_open
from src.discovery import search_jobs, print_jobs_table
from src.applier import apply_to_job

app = typer.Typer(
    name="browser-job-agent",
    help="Command-Driven AI Browser Agent for Automated Job Discovery & Applications",
    add_completion=False
)
console = Console()

@app.command("launch-chrome")
def launch_chrome_cmd(
    port: int = typer.Option(9222, "--port", "-p", help="Remote debugging port for Chrome"),
    profile_dir: Optional[str] = typer.Option(None, "--profile-dir", help="Custom Chrome profile path")
):
    """
    Launch Google Chrome on macOS with remote debugging enabled.
    Log into LinkedIn once here, and the agent will use this authenticated session!
    """
    if is_chrome_debugging_port_open(port):
        console.print(f"[bold green]✓ Chrome is already running with remote debugging on port {port}![/bold green]")
        return

    launch_local_chrome(port=port, profile_dir=profile_dir)
    console.print(Panel(
        f"[bold green]Chrome launched on port {port}![/bold green]\n"
        "1. Open [cyan]https://www.linkedin.com[/cyan] in this Chrome window and log in if you haven't already.\n"
        "2. Keep this Chrome window open.\n"
        "3. Now run [bold yellow]python cli.py apply --url <JOB_URL>[/bold yellow] and the agent will use your logged-in session!",
        title="Session Ready",
        border_style="green"
    ))

@app.command("search")
def search_cmd(
    query: str = typer.Argument(..., help="Job title or keywords (e.g. 'Senior Python Engineer')"),
    location: str = typer.Option("Remote", "--location", "-l", help="Job location or 'Remote'"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of job results to fetch"),
    site: List[str] = typer.Option(["linkedin", "indeed", "glassdoor"], "--site", "-s", help="Job sites to search"),
    remote_only: bool = typer.Option(False, "--remote-only", help="Filter for remote jobs only"),
    save_json: Optional[str] = typer.Option(None, "--save", help="Optional path to save results as JSON")
):
    """
    Fast search for job postings across LinkedIn, Indeed, and Glassdoor without burning LLM tokens.
    """
    jobs = search_jobs(
        search_term=query,
        location=location,
        sites=site,
        results_wanted=limit,
        is_remote=remote_only
    )
    print_jobs_table(jobs)

    if save_json and jobs:
        output_path = Path(save_json)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2)
        console.print(f"[green]Saved {len(jobs)} jobs to {output_path}[/green]")

@app.command("apply")
def apply_cmd(
    url: str = typer.Option(..., "--url", "-u", help="Job URL or career portal posting to apply to"),
    dry_run: bool = typer.Option(True, "--dry-run/--live", help="Pause before clicking the final submit button (recommended)"),
    connect_chrome: bool = typer.Option(True, "--connect-chrome/--standalone", help="Attach to running Chrome (port 9222) if available"),
    headless: bool = typer.Option(False, "--headless/--headful", help="Run browser headlessly (default: headful to watch live)"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Custom candidate profile JSON path")
):
    """
    Direct the AI browser agent to navigate to a job posting, fill out the application, and attach resume.
    """
    asyncio.run(
        apply_to_job(
            job_url=url,
            dry_run=dry_run,
            profile_path=profile,
            connect_existing_chrome=connect_chrome,
            headless=headless
        )
    )

@app.command("search-and-apply")
def search_and_apply_cmd(
    query: str = typer.Argument(..., help="Job title or keywords to search for"),
    location: str = typer.Option("Remote", "--location", "-l", help="Job location or 'Remote'"),
    limit: int = typer.Option(5, "--limit", "-n", help="Number of jobs to search for"),
    dry_run: bool = typer.Option(True, "--dry-run/--live", help="Pause before clicking the final submit button")
):
    """
    Interactive flow: Search for matching jobs, select one from the list, and immediately trigger the agent!
    """
    jobs = search_jobs(search_term=query, location=location, results_wanted=limit)
    if not jobs:
        console.print("[red]No jobs found to apply for.[/red]")
        return

    print_jobs_table(jobs)
    choice = typer.prompt(f"Enter job number to apply (1-{len(jobs)}) or 'q' to cancel", default="1")
    if choice.strip().lower() == 'q':
        console.print("[yellow]Cancelled.[/yellow]")
        return

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(jobs):
            target_job = jobs[idx]
            console.print(f"[bold green]Selected: {target_job['title']} at {target_job['company']}[/bold green]")
            asyncio.run(
                apply_to_job(
                    job_url=target_job["job_url"],
                    dry_run=dry_run
                )
            )
        else:
            console.print("[red]Invalid index selected.[/red]")
    except ValueError:
        console.print("[red]Invalid input.[/red]")

@app.command("check-profile")
def check_profile_cmd(
    profile_path: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile path to validate")
):
    """
    Inspect and validate candidate profile data and verify the resume PDF exists.
    """
    try:
        data = get_candidate_profile(profile_path)
        console.print(Panel(json.dumps(data, indent=2), title="Candidate Profile", border_style="cyan"))

        resume_path = BASE_DIR / data.get("resume_file_path", "")
        if resume_path.exists():
            console.print(f"[bold green]✓ Resume file verified at:[/bold green] {resume_path}")
        else:
            console.print(f"[bold red]✗ Resume file NOT found at:[/bold red] {resume_path}")
    except Exception as e:
        console.print(f"[bold red]Profile validation failed: {e}[/bold red]")

@app.command("server")
def server_cmd(
    port: int = typer.Option(8000, "--port", "-p", help="Port to run the FastAPI bridge on"),
    host: str = typer.Option("127.0.0.1", "--host", "-h", help="Host interface")
):
    """
    Start the local Job Co-Pilot bridge server (powers the Chrome Extension side panel).
    """
    import uvicorn
    console.print(f"[bold green]Starting Job Co-Pilot bridge server on http://{host}:{port}...[/bold green]")
    uvicorn.run("server:app", host=host, port=port, reload=True)

if __name__ == "__main__":
    app()

