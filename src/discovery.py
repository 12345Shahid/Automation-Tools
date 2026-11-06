import logging
from typing import List, Dict, Any, Optional
import pandas as pd
from rich.console import Console
from rich.table import Table

console = Console()
# Suppress noisy logs from third-party scrapers
logging.getLogger("jobspy").setLevel(logging.WARNING)

def search_jobs(
    search_term: str,
    location: str = "Remote",
    country: str = "usa",
    job_type: Optional[str] = "fulltime",
    sites: Optional[List[str]] = None,
    results_wanted: int = 10,
    hours_old: int = 168, # Past week by default
    is_remote: bool = False
) -> List[Dict[str, Any]]:
    """
    Search job postings across LinkedIn, Indeed, Glassdoor, and ZipRecruiter using JobSpy.
    Returns a clean list of structured job postings with direct application links.
    """
    from jobspy import scrape_jobs

    if sites is None:
        sites = ["linkedin", "indeed", "glassdoor"]

    target_job_type = None
    if job_type and job_type.lower() not in ("any", "all", "none", ""):
        target_job_type = job_type.lower()

    target_country = (country or "usa").lower()

    console.print(f"[cyan]Searching {sites} for '{search_term}' (type: {target_job_type or 'all'}, country: {target_country}) in '{location}' (limit: {results_wanted})...[/cyan]")

    try:
        jobs_df: pd.DataFrame = scrape_jobs(
            site_name=sites,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            hours_old=hours_old,
            is_remote=is_remote,
            job_type=target_job_type,
            country_indeed=target_country
        )
    except Exception as e:
        console.print(f"[red]Error while fetching jobs with JobSpy: {e}[/red]")
        return []

    if jobs_df.empty:
        console.print("[yellow]No jobs found matching the criteria.[/yellow]")
        return []

    # Format into list of dicts
    formatted_jobs = []
    for _, row in jobs_df.iterrows():
        job_data = {
            "title": str(row.get("title", "N/A")),
            "company": str(row.get("company", "N/A")),
            "location": str(row.get("location", "N/A")),
            "site": str(row.get("site", "N/A")),
            "job_type": str(row.get("job_type", target_job_type or "Full-time")),
            "job_url": str(row.get("job_url", "")),
            "date_posted": str(row.get("date_posted", "N/A")),
            "is_remote": bool(row.get("is_remote", False)),
            "description": str(row.get("description", ""))[:300] + "..." if row.get("description") else ""
        }
        if job_data["job_url"]:
            formatted_jobs.append(job_data)

    return formatted_jobs

def print_jobs_table(jobs: List[Dict[str, Any]]) -> None:
    """Print jobs list in a nice terminal table."""
    if not jobs:
        console.print("[yellow]No jobs to display.[/yellow]")
        return

    table = Table(title="Discovered Jobs", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Company", style="bold cyan", width=20)
    table.add_column("Title", style="bold white", width=30)
    table.add_column("Location", style="green", width=18)
    table.add_column("Platform", style="magenta", width=12)
    table.add_column("Job URL", style="blue underline", overflow="fold")

    for idx, job in enumerate(jobs, 1):
        table.add_row(
            str(idx),
            job["company"],
            job["title"],
            job["location"],
            job["site"],
            job["job_url"]
        )

    console.print(table)
