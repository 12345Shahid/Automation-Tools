import asyncio
import json
from pathlib import Path
from typing import Optional, Dict, Any
from rich.console import Console

from browser_use import Agent, Browser
from src.config import get_candidate_profile, get_llm, BASE_DIR
from src.browser_bridge import get_browser

console = Console()

def generate_job_application_task(job_url: str, profile: Dict[str, Any], dry_run: bool = True) -> str:
    """
    Generate a precise, structured task prompt for the browser agent
    incorporating the candidate profile and safety rules.
    """
    personal = profile.get("personal", {})
    socials = profile.get("socials", {})
    auth = profile.get("work_authorization", {})
    exp = profile.get("experience_and_preferences", {})
    edu = profile.get("education", {})
    screening = profile.get("screening_defaults", {})

    dry_run_instruction = """
IMPORTANT SAFETY RULE (DRY RUN / PAUSE BEFORE SUBMIT):
- Fill out all form fields, upload the resume, and answer all questions sequentially across all multi-page steps.
- When you reach the final step or the final 'Submit Application' button:
  DO NOT click the final 'Submit' or 'Apply' button!
  Instead, leave the browser on the review/submit page and call the done action with a summary of the filled information so the user can verify.
""" if dry_run else """
SUBMIT RULE:
- Fill out all form fields, upload resume, navigate multi-page steps, and on the final review step, click Submit to complete the application.
"""

    task = f"""
Navigate to {job_url} and apply for the job using the following candidate profile:

### CANDIDATE PROFILE:
Personal Details:
- First Name: {personal.get('first_name', '')}
- Last Name: {personal.get('last_name', '')}
- Full Name: {personal.get('full_name', '')}
- Email: {personal.get('email', '')}
- Phone: {personal.get('phone', '')}
- Address: {personal.get('address', '')}, {personal.get('city', '')}, {personal.get('state', '')} {personal.get('postal_code', '')}, {personal.get('country', '')}

Links:
- LinkedIn: {socials.get('linkedin', '')}
- GitHub: {socials.get('github', '')}
- Portfolio: {socials.get('portfolio', '')}

Work Authorization:
- Legally authorized to work in this country: {auth.get('legally_authorized_to_work', 'Yes')}
- Requires sponsorship now: {auth.get('requires_sponsorship', 'No')}
- Will require sponsorship in the future: {auth.get('will_require_sponsorship_future', 'No')}
- Citizenship / Status: {auth.get('visa_type', 'Citizen / Permanent Resident')}

Professional Background & Preferences:
- Current Title: {exp.get('current_title', '')}
- Total Years Experience: {exp.get('total_years_experience', '')}
- Desired Salary: ${exp.get('desired_salary_usd', '')}
- Notice Period: {exp.get('notice_period', '2 weeks')}
- Willing to Relocate: {exp.get('willing_to_relocate', 'No')}
- Open to Remote: {exp.get('open_to_remote', 'Yes')}
- Primary Skills: {', '.join(exp.get('primary_skills', []))}

Education:
- Degree: {edu.get('degree', '')} in {edu.get('field_of_study', '')}
- Institution: {edu.get('school', '')} (Graduation: {edu.get('graduation_year', '')}, GPA: {edu.get('gpa', '')})

Demographics & Screening Defaults:
- Summary / Cover Letter snippet: "{screening.get('summary_elevator_pitch', '')}"
- Gender: {screening.get('gender', 'Prefer not to disclose')}
- Race / Ethnicity: {screening.get('race_ethnicity', 'Decline to state')}
- Veteran Status: {screening.get('veteran_status', 'I am not a protected veteran')}
- Disability Status: {screening.get('disability_status', 'No, I do not have a disability')}

### APPLICATION WORKFLOW:
1. If there is an 'Easy Apply', 'Apply with LinkedIn', or 'Apply Now' button, click it.
2. If this is a LinkedIn Easy Apply:
   - Fill in contact info and upload the resume when requested.
   - For screening questions, match the closest answer from the profile above.
   - Click 'Next' or 'Review' to proceed through steps.
3. If this is an external ATS (Workday, Greenhouse, Lever, Ashby, BambooHR):
   - Fill in each input field sequentially (First name, Last name, Email, Phone, LinkedIn URL, Portfolio).
   - If there is a file upload input for Resume/CV, upload the file from the available file paths.
   - If prompted for cover letter, paste the elevator pitch snippet.
4. Answer any dropdowns or radio buttons according to the candidate profile.

{dry_run_instruction}
"""
    return task

async def apply_to_job(
    job_url: str,
    dry_run: bool = True,
    profile_path: Optional[str] = None,
    connect_existing_chrome: bool = True,
    headless: bool = False
) -> Any:
    """
    Run the browser agent to apply for a job at the given URL.
    """
    profile = get_candidate_profile(profile_path)
    llm = get_llm()

    # Determine resume file path
    resume_rel = profile.get("resume_file_path", "data/resumes/sample_resume.pdf")
    resume_path = BASE_DIR / resume_rel
    available_files = []
    if resume_path.exists():
        available_files.append(str(resume_path.resolve()))
        console.print(f"[green]✓ Attached resume file:[/green] {resume_path.resolve()}")
    else:
        console.print(f"[yellow]Warning: Resume file not found at {resume_path}. Application will proceed without file attachment.[/yellow]")

    browser = get_browser(
        connect_existing_chrome=connect_existing_chrome,
        headless=headless
    )

    task_prompt = generate_job_application_task(job_url, profile, dry_run=dry_run)

    console.print(f"\n[bold cyan]Starting Job Application Agent[/bold cyan]")
    console.print(f"Target URL: [blue]{job_url}[/blue]")
    console.print(f"Mode: [bold {'yellow' if dry_run else 'red'}]{'DRY RUN (Pause before submit)' if dry_run else 'LIVE SUBMIT'}[/bold {'yellow' if dry_run else 'red'}]\n")

    agent = Agent(
        task=task_prompt,
        llm=llm,
        browser=browser,
        available_file_paths=available_files,
        use_vision=True,
        max_actions_per_step=4
    )

    history = await agent.run()
    return history
