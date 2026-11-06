import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import get_candidate_profile, get_llm, BASE_DIR
from src.discovery import search_jobs
from src.email_sender import EmailSender
from src.email_writer import generate_outreach_email
from src.email_reader import EmailReader
from src.email_chat_engine import EmailChatEngine
from src.lead_scraper import LeadScraper
from src.ai_provider import load_ai_config, save_ai_config, test_provider_connection, PROVIDERS

app = FastAPI(title="Job Co-Pilot Bridge Server", version="1.0.0")

# Enable CORS for Chrome Extension
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/email-agent")
def email_agent_dashboard():
    dashboard_file = BASE_DIR / "static" / "email_agent.html"
    if not dashboard_file.exists():
        raise HTTPException(status_code=404, detail="Email Agent dashboard file not found")
    return FileResponse(dashboard_file)

@app.get("/test")
def test_page():
    test_file = BASE_DIR / "extension" / "test_job_form.html"
    return FileResponse(test_file)

@app.get("/skool-test")
def skool_test_page():
    test_file = BASE_DIR / "skool-agent" / "test_skool_community.html"
    return FileResponse(test_file)

@app.get("/api/resume.pdf")
def get_resume_pdf():
    profile = get_candidate_profile()
    resume_path = BASE_DIR / profile.get("resume_file_path", "data/resumes/sample_resume.pdf")
    if not resume_path.exists():
        raise HTTPException(status_code=404, detail=f"Resume file not found at {resume_path}")
    return FileResponse(
        resume_path,
        media_type="application/pdf",
        filename=resume_path.name
    )

@app.get("/api/resume-base64")
def get_resume_base64():
    import base64
    profile = get_candidate_profile()
    resume_path = BASE_DIR / profile.get("resume_file_path", "data/resumes/sample_resume.pdf")
    if not resume_path.exists():
        raise HTTPException(status_code=404, detail=f"Resume file not found at {resume_path}")
    with open(resume_path, "rb") as f:
        data_b64 = base64.b64encode(f.read()).decode("utf-8")
    return {
        "success": True,
        "filename": resume_path.name,
        "data": data_b64,
        "size": resume_path.stat().st_size
    }

class LogMessage(BaseModel):
    event: str
    element: Optional[str] = None
    value: Optional[str] = None
    details: Optional[str] = None

@app.post("/api/test-log")
def log_event(log: LogMessage):
    from rich.console import Console
    console = Console()
    console.print(f"[bold cyan][BROWSER EVENT][/bold cyan] [yellow]{log.event}[/yellow] | element: [green]{log.element}[/green] | value: [white]{log.value}[/white] | details: [dim]{log.details}[/dim]")
    return {"status": "logged"}



class SearchRequest(BaseModel):
    query: str
    location: str = "Remote"
    country: str = "usa"
    job_type: Optional[str] = "fulltime"
    limit: int = 10
    sites: Optional[List[str]] = ["linkedin", "indeed", "glassdoor"]
    is_remote: bool = False

class MatchRequest(BaseModel):
    fields: List[Dict[str, Any]]
    profile_override: Optional[Dict[str, Any]] = None

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "job-copilot-bridge"}

@app.get("/api/profile")
def get_profile():
    try:
        profile = get_candidate_profile()
        return {"success": True, "profile": profile}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/profile")
def update_profile(new_profile: Dict[str, Any]):
    try:
        profile_path = BASE_DIR / "data" / "candidate_profile.json"
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(new_profile, f, indent=2)
        return {"success": True, "message": "Profile updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/jobs/search")
def search_jobs_endpoint(req: SearchRequest):
    try:
        jobs = search_jobs(
            search_term=req.query,
            location=req.location,
            country=req.country,
            job_type=req.job_type,
            sites=req.sites,
            results_wanted=req.limit,
            is_remote=req.is_remote
        )
        return {"success": True, "count": len(jobs), "jobs": jobs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/match-fields")
def match_fields_endpoint(req: MatchRequest):
    """
    Takes detected form fields from the Chrome page and maps them to candidate profile data.
    Uses ultra-fast, cheap text LLM reasoning.
    """
    import datetime
    today = datetime.date.today()
    two_weeks = today + datetime.timedelta(days=14)
    
    profile = req.profile_override or get_candidate_profile()
    
    prompt = f"""
You are an intelligent job application autofill engine.
Map the provided HTML form fields to the candidate profile data.

CANDIDATE PROFILE:
{json.dumps(profile, indent=2)}

DETECTED FORM FIELDS:
{json.dumps(req.fields, indent=2)}

DATE CONTEXT:
- Today's date: {today.strftime('%Y-%m-%d')} ({today.strftime('%m/%d/%Y')})
- 2 weeks from now: {two_weeks.strftime('%Y-%m-%d')} ({two_weeks.strftime('%m/%d/%Y')})

INSTRUCTIONS:
1. For each field in the form, determine the best value to fill based on the candidate profile.
2. EMPLOYER / EXPERIENCE SECTION:
   - "Company", "Company/Business name", "Employer name", "Organization": use candidate's company ("Acme Innovations Inc.").
   - "Designation", "Title", "Job Title", "Position": use candidate's title ("Senior Full-Stack Engineer").
   - "Start date" or "From" for work experience: use candidate's employment start date ("2020-11-01" or "November 01, 2020" or "11/01/2020").
   - "I currently work here" / "Current Job": true (or "Yes").
   - "End date" for current job: leave blank "" or "Present".
3. EDUCATION SECTION:
   - "Degree": use "Bachelor of Science".
   - "Field of study", "Major": use "Computer Science".
   - "Institution", "School name", "University": use "University of California, Berkeley".
   - "Start date" or "From" in Education: use candidate's education start date ("2015-08-20" or "August 20, 2015" or "08/20/2015" or "2015").
   - "End date", "Graduation date", "To" in Education: use candidate's graduation date ("2019-05-15" or "May 15, 2019" or "05/15/2019" or "05/2019" or "2019"). NEVER use today's date or 2026 for a completed college degree!
   - "Currently pursuing": false (or "No").
   - "Grade", "GPA": use "3.8".
4. JOB AVAILABILITY / NOTICE PERIOD:
   - Only for fields asking when candidate can join this new job (e.g. "Earliest Start Date", "Availability", "Notice Period"): use "{two_weeks.strftime('%Y-%m-%d')}" or "{two_weeks.strftime('%m/%d/%Y')}" or "2 weeks".
5. WORK AUTHORIZATION & GENERAL:
   - Legally authorized to work: Yes.
   - Requires visa sponsorship: No.
6. DATE FORMATTING:
   - If input type is "date", return "YYYY-MM-DD".
   - If placeholder/label indicates "MM/YYYY", return "MM/YYYY" (e.g. "05/2019" or "11/2020").
   - If placeholder/label indicates "MM/DD/YYYY", return "MM/DD/YYYY" (e.g. "11/01/2020").
   - If placeholder/label indicates "DD/MM/YYYY", return "DD/MM/YYYY".
   - If dropdown/select asks for Month: choose month name (e.g. "August" or "November" or "08" or "11").
   - If dropdown/select asks for Year: choose 4-digit year (e.g. "2015", "2019", "2020").
7. RESUME UPLOAD:
   - For file inputs or fields asking for resume/CV: ALWAYS return "__AUTO_UPLOAD_RESUME__".
8. Return ONLY a valid JSON object with key "matches", mapping field "id" (or "name") to value:
Example:
{{
  "matches": {{
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane.doe@example.com",
    "start_date": "{two_weeks.strftime('%Y-%m-%d')}",
    "resume_file": "__AUTO_UPLOAD_RESUME__"
  }}
}}
"""
    try:
        kie_key = os.getenv("KIE_API_KEY")
        if kie_key:
            from src.config import call_kie_deepseek
            content = call_kie_deepseek(prompt)
        else:
            llm = get_llm()
            response = llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
        
        # Clean markdown codeblocks if present
        cleaned = content.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        
        data = json.loads(cleaned.strip())
        return {"success": True, "matches": data.get("matches", {})}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error matching fields: {e}")

class EmailPreviewRequest(BaseModel):
    raw_text: Optional[str] = None
    items: Optional[List[Dict[str, str]]] = None

class EmailSendItem(BaseModel):
    email: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    force: bool = True

class EmailSendRequest(BaseModel):
    items: List[EmailSendItem]

@app.get("/api/email/status")
def get_email_status():
    sender = EmailSender()
    ok, msg = sender.test_connection()
    return {
        "smtp_ok": ok,
        "message": msg,
        "sender_name": sender.sender_name,
        "sender_email": sender.sender_email,
        "host": sender.host,
        "port": sender.port
    }

@app.post("/api/email/test-smtp")
def api_test_smtp():
    sender = EmailSender()
    ok, msg = sender.test_connection()
    return {"success": ok, "message": msg}

@app.post("/api/email/preview")
def preview_emails(req: EmailPreviewRequest):
    sender = EmailSender()
    leads = []
    if req.raw_text:
        lines = req.raw_text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(",")]
            leads.append({
                "email": parts[0],
                "name": parts[1] if len(parts) > 1 else "",
                "company": parts[2] if len(parts) > 2 else "",
                "notes": parts[3] if len(parts) > 3 else ""
            })
    elif req.items:
        leads = req.items

    drafts = []
    for lead in leads:
        email = lead.get("email", "").strip()
        if not email:
            continue
        draft = generate_outreach_email(
            email=email,
            name=lead.get("name"),
            company=lead.get("company"),
            custom_notes=lead.get("notes")
        )
        drafts.append({
            "email": email,
            "name": lead.get("name", ""),
            "company": lead.get("company", ""),
            "subject": draft["subject"],
            "body_text": draft["body_text"],
            "body_html": draft["body_html"],
            "already_sent": sender.is_already_sent(email)
        })

    return {"success": True, "count": len(drafts), "drafts": drafts}

@app.post("/api/email/send")
def send_emails(req: EmailSendRequest):
    sender = EmailSender()
    results = {"sent": 0, "skipped": 0, "failed": 0, "details": []}
    for item in req.items:
        res = sender.send_email(
            to_email=item.email,
            subject=item.subject,
            body_text=item.body_text,
            body_html=item.body_html,
            force=item.force
        )
        results["details"].append(res)
        if res.get("success"):
            results["sent"] += 1
        elif res.get("skipped"):
            results["skipped"] += 1
        else:
            results["failed"] += 1
    return results

@app.get("/api/email/history")
def get_email_history():
    sender = EmailSender()
    return sender.get_history()

class EmailChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = None

class EmailSearchRequest(BaseModel):
    query: Optional[str] = None
    from_address: Optional[str] = None
    subject_keyword: Optional[str] = None
    body_keyword: Optional[str] = None
    limit: int = 10

@app.post("/api/email/chat")
def chat_with_email_agent(req: EmailChatRequest):
    engine = EmailChatEngine()
    result = engine.process_chat(req.message, req.history)
    return result

@app.get("/api/email/inbox")
def get_inbox_emails(limit: int = 10):
    reader = EmailReader()
    try:
        emails = reader.fetch_recent_emails(limit=limit)
        return {"success": True, "count": len(emails), "emails": emails}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/email/search")
def search_inbox_emails(req: EmailSearchRequest):
    reader = EmailReader()
    try:
        results = reader.search_emails(
            query=req.query,
            from_address=req.from_address,
            subject_keyword=req.subject_keyword,
            body_keyword=req.body_keyword,
            limit=req.limit
        )
        return {"success": True, "count": len(results), "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class LeadScrapeRequest(BaseModel):
    industry: str = "roofing contractors"
    location: str = "Dallas, TX"
    count: int = 10
    no_website_only: bool = True

class LeadExportRequest(BaseModel):
    leads: List[Dict[str, Any]]
    filename: Optional[str] = "scraped_leads.csv"

@app.post("/api/leads/scrape")
def api_scrape_leads(req: LeadScrapeRequest):
    scraper = LeadScraper()
    try:
        if any(w in req.industry.lower() for w in ["it", "software", "tech", "agency", "consulting"]):
            leads = scraper.find_it_companies(query=req.industry, location=req.location, count=req.count)
        else:
            leads = scraper.find_local_businesses(
                industry=req.industry,
                location=req.location,
                count=req.count,
                no_website_only=req.no_website_only
            )
        return {"success": True, "count": len(leads), "leads": leads}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/leads/export")
def api_export_leads(req: LeadExportRequest):
    scraper = LeadScraper()
    try:
        csv_path = scraper.export_to_csv(req.leads, req.filename or "scraped_leads.csv")
        return {"success": True, "path": str(csv_path), "filename": csv_path.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class AIConfigUpdateRequest(BaseModel):
    provider: str
    api_key: Optional[str] = None
    model: Optional[str] = None

class AITestRequest(BaseModel):
    provider: str
    api_key: str
    model: Optional[str] = None

@app.get("/api/ai/config")
def get_ai_config():
    config = load_ai_config()
    raw_key = config.get("api_key", "")
    masked_key = ""
    if raw_key:
        if len(raw_key) > 8:
            masked_key = raw_key[:4] + "..." + raw_key[-4:]
        else:
            masked_key = "****"
    
    return {
        "current_provider": config.get("provider", "offline"),
        "current_model": config.get("model", ""),
        "has_api_key": bool(raw_key),
        "masked_api_key": masked_key,
        "providers": PROVIDERS
    }

@app.post("/api/ai/config")
def update_ai_config(req: AIConfigUpdateRequest):
    try:
        updated = save_ai_config(req.provider, req.api_key, req.model)
        return {"success": True, "config": updated}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/ai/test")
def test_ai_connection_endpoint(req: AITestRequest):
    result = test_provider_connection(req.provider, req.api_key, req.model)
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
