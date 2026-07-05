# ============================================================
# backend/api.py — FastAPI Application
# ============================================================
# REST API for the AI Resume Screening Platform.
#
# ARCHITECTURE (refactored):
#   FastAPI handles ONLY AI-related work:
#     - Resume parsing (PDF/DOCX → text)
#     - Gemini 2.5 Flash extraction
#     - JD matching / ATS scoring
#     - Candidate storage (Airtable)
#
#   All workflow automation is delegated to n8n via webhook:
#     - Google Calendar event creation
#     - Google Meet link generation
#     - Gmail interview invitation
#     - Airtable status update
#
# Endpoints:
#   POST /parse_resume              — extract structured data from a resume
#   POST /match_resume              — full AI pipeline: parse → match → score → store → notify n8n
#   POST /schedule_interview        — manual interview schedule (calls n8n webhook)
#   GET  /candidate/{id}            — get candidate details
#   PUT  /candidate/{id}/override   — recruiter overrides AI status
#   GET  /health                    — health check
#   GET  /stats                     — pipeline statistics
#   POST /webhook/process_resume    — n8n entry point (same as /match_resume)
# ============================================================

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ai.jd_matcher import match_resume_to_jd
from ai.resume_parser import GeminiError, parse_resume_with_ai
from ai.scoring import ApplicationStatus, apply_override, determine_status
from backend.config import settings
from backend.n8n_webhook import WebhookPayload, notify_n8n
from database.airtable import CandidateRecord, get_repository
from database.redis_cache import get_cache
from parser import parse_resume_bytes, parse_resume_file
from utils.logger import logger
from utils.validators import ValidationError, validate_file_extension

# ------------------------------------------------------------------
# App setup
# ------------------------------------------------------------------
app = FastAPI(
    title="AI Resume Screening & Interview Scheduling API",
    description="AI-powered recruitment pipeline: parse, match, score, store. "
                "Workflow automation delegated to n8n.",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    root_path="/api",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(",") if settings.allowed_origins != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------
# Pydantic models
# ------------------------------------------------------------------
class JDMatchRequest(BaseModel):
    candidate_data: dict = Field(..., description="Structured candidate data from /parse_resume")
    jd_text: str = Field(..., description="Job description text")


class ScheduleInterviewRequest(BaseModel):
    candidate_id: str = Field(..., description="Airtable/mock record ID")
    date: Optional[str] = Field(None, description="ISO datetime, e.g. 2025-07-10T09:00:00Z")
    interviewer_email: str = ""


class OverrideRequest(BaseModel):
    new_status: str = Field(..., description="Shortlisted | Manual Review | Rejected | Interview Scheduled")
    recruiter: str = ""
    note: str = ""


class CandidateResponse(BaseModel):
    id: str
    candidate_name: str = ""
    email: str = ""
    phone: str = ""
    experience: str = ""
    skills: list[str] = []
    match_score: int = 0
    matching_skills: list[str] = []
    missing_skills: list[str] = []
    ai_summary: str = ""
    recommendation: str = ""
    application_status: str = ""
    recruiter_notes: str = ""
    interview_status: str = ""
    interview_date: str = ""
    interview_link: str = ""
    created_time: str = ""
    updated_time: str = ""


# ------------------------------------------------------------------
# Exception handlers
# ------------------------------------------------------------------
@app.exception_handler(ValidationError)
async def validation_error_handler(request, exc: ValidationError):
    logger.event("validation_error", level=40, error=str(exc))
    return JSONResponse(status_code=400, content={"error": "validation_error", "detail": str(exc)})


@app.exception_handler(GeminiError)
async def gemini_error_handler(request, exc: GeminiError):
    logger.event("gemini_error", level=40, error=str(exc))
    return JSONResponse(status_code=503, content={"error": "ai_error", "detail": str(exc)})


# ------------------------------------------------------------------
# AI Pipeline orchestrator
# ------------------------------------------------------------------
# After refactoring, FastAPI does ONLY:
#   1. AI extraction (Gemini)
#   2. JD matching
#   3. ATS scoring
#   4. Candidate storage (Airtable)
#   5. Notify n8n via webhook (workflow automation lives there)
# ------------------------------------------------------------------
def run_full_pipeline(resume_text: str, jd_text: str) -> CandidateRecord:
    """
    Full AI pipeline: parse → match → score → store → notify n8n.

    This function is AI-only. It does NOT:
      - Send Gmail
      - Create Google Calendar events
      - Generate Google Meet links

    Instead it sends candidate JSON to the n8n webhook which handles
    all workflow automation asynchronously.
    """
    logger.event("pipeline_start", resume_chars=len(resume_text), jd_chars=len(jd_text))

    # 1. AI extraction (Gemini 2.5 Flash)
    candidate_data = parse_resume_with_ai(resume_text)
    logger.event("pipeline_extracted", name=candidate_data.get("name"))

    # 2. JD matching
    match_result = match_resume_to_jd(candidate_data, jd_text)
    logger.event("pipeline_matched", score=match_result.get("match_score"))

    # 3. Business rules — determine application status
    status = determine_status(match_result.get("match_score", 0))

    # 4. Store in Airtable (or mock)
    repo = get_repository()
    record = CandidateRecord(
        candidate_name=candidate_data.get("name", ""),
        email=candidate_data.get("email", ""),
        phone=candidate_data.get("phone", ""),
        experience=str(candidate_data.get("experience", "")),
        skills=candidate_data.get("skills", []),
        match_score=match_result.get("match_score", 0),
        matching_skills=match_result.get("matching_skills", []),
        missing_skills=match_result.get("missing_skills", []),
        ai_summary=match_result.get("ai_summary", ""),
        recommendation=match_result.get("hiring_recommendation", ""),
        application_status=status.value,
        resume_text=resume_text,
    )
    record_id = repo.create(record)
    record.id = record_id

    # 5. Delegate workflow automation to n8n via webhook
    webhook_result = _notify_n8n(record)
    logger.event("pipeline_done", record_id=record_id, status=record.application_status,
                 webhook_status=webhook_result.get("status"))

    return record


def _notify_n8n(record: CandidateRecord) -> dict:
    """
    Build a WebhookPayload from the stored candidate record and send
    it to the n8n webhook.  Never raises — failure is logged and
    returned as a result dict so the AI pipeline result is intact.
    """
    payload = WebhookPayload(
        candidate_name=record.candidate_name,
        email=record.email,
        phone=record.phone,
        match_score=record.match_score,
        application_status=record.application_status,
        candidate_id=record.id,
        skills=record.skills,
        matching_skills=record.matching_skills,
        missing_skills=record.missing_skills,
        ai_summary=record.ai_summary,
        recommendation=record.recommendation,
    )
    return notify_n8n(payload)


# ------------------------------------------------------------------
# ENDPOINTS
# ------------------------------------------------------------------

@app.get("/health")
async def health():
    """Health check — returns service status and config flags."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "time": datetime.now(timezone.utc).isoformat(),
        "version": "2.0.0",
        "config": {
            "gemini_configured": bool(settings.gemini_api_key),
            "airtable_configured": bool(settings.airtable_api_key and settings.airtable_base_id),
            "redis_url": settings.redis_url.split("@")[-1] if "@" in settings.redis_url else settings.redis_url,
            "google_oauth_configured": bool(settings.google_client_id),
            "cache_enabled": settings.cache_enabled,
            "n8n_webhook_configured": bool(settings.n8n_webhook_url),
        },
    }


@app.post("/parse_resume")
async def parse_resume(file: UploadFile = File(...)):
    """
    Upload a resume (PDF/DOCX) and extract structured data via Gemini 2.5 Flash.
    Returns the structured candidate JSON.

    AI-only: no email/calendar logic.
    """
    logger.event("endpoint_call", endpoint="/parse_resume", filename=file.filename)

    # Validate file type
    try:
        validate_file_extension(file.filename or "")
    except ValidationError:
        raise HTTPException(status_code=400, detail=f"Unsupported file: {file.filename}")

    file_bytes = await file.read()
    try:
        resume_text = parse_resume_bytes(file.filename, file_bytes)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.event("parse_error", level=40, error=str(exc))
        raise HTTPException(status_code=422, detail=f"Failed to parse file: {exc}")

    try:
        candidate_data = parse_resume_with_ai(resume_text)
    except GeminiError as exc:
        raise HTTPException(status_code=503, detail=f"AI parsing failed: {exc}")

    return {
        "status": "success",
        "filename": file.filename,
        "candidate": candidate_data,
    }


@app.post("/match_resume")
async def match_resume(
    file: UploadFile = File(..., description="Resume file (PDF/DOCX)"),
    jd_text: str = Form(..., description="Job description text"),
):
    """
    Upload a resume + JD text, run the full AI pipeline:
    parse → match → score → store → notify n8n.

    This endpoint does NOT send emails or schedule interviews directly.
    Workflow automation is delegated to the n8n webhook.
    """
    logger.event("endpoint_call", endpoint="/match_resume", filename=file.filename)

    try:
        validate_file_extension(file.filename or "")
    except ValidationError:
        raise HTTPException(status_code=400, detail=f"Unsupported file: {file.filename}")

    file_bytes = await file.read()
    try:
        resume_text = parse_resume_bytes(file.filename, file_bytes)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.event("parse_error", level=40, error=str(exc))
        raise HTTPException(status_code=422, detail=f"Failed to parse: {exc}")

    try:
        record = run_full_pipeline(resume_text, jd_text)
    except GeminiError as exc:
        raise HTTPException(status_code=503, detail=f"AI failed: {exc}")

    return {
        "status": "success",
        "candidate": record.to_dict(),
        "workflow": "n8n webhook notified for automation",
    }


@app.post("/schedule_interview")
async def schedule_interview(req: ScheduleInterviewRequest):
    """
    Manually trigger interview scheduling by sending a webhook
    notification to n8n, which handles Calendar + Meet + Gmail.

    FastAPI itself does NOT create calendar events or send emails.
    """
    logger.event("endpoint_call", endpoint="/schedule_interview", candidate_id=req.candidate_id)

    repo = get_repository()
    record = repo.get_by_id(req.candidate_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    # Build payload and send to n8n
    payload = WebhookPayload(
        candidate_name=record.candidate_name,
        email=record.email,
        phone=record.phone,
        match_score=record.match_score,
        application_status="Interview Requested",
        candidate_id=record.id,
        skills=record.skills,
        matching_skills=record.matching_skills,
        missing_skills=record.missing_skills,
        ai_summary=record.ai_summary,
        recommendation=record.recommendation,
    )
    result = notify_n8n(payload)

    return {
        "status": "success",
        "message": "Interview scheduling delegated to n8n workflow",
        "webhook_result": result,
    }


@app.get("/candidate/{candidate_id}")
async def get_candidate(candidate_id: str):
    """Get full candidate details by record ID."""
    logger.event("endpoint_call", endpoint="/candidate", candidate_id=candidate_id)
    repo = get_repository()
    record = repo.get_by_id(candidate_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return record.to_dict()


@app.get("/candidates")
async def list_candidates():
    """List all candidates."""
    repo = get_repository()
    records = repo.list_all()
    return {"count": len(records), "candidates": [r.to_dict() for r in records]}


@app.put("/candidate/{candidate_id}/override")
async def override_status(candidate_id: str, req: OverrideRequest):
    """Recruiter overrides the AI-determined status."""
    logger.event("endpoint_call", endpoint="/override", candidate_id=candidate_id)

    repo = get_repository()
    record = repo.get_by_id(candidate_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    try:
        new_status = apply_override(
            record.application_status, req.new_status, req.recruiter, req.note
        )
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status: {req.new_status}")

    repo.update(candidate_id, {
        "Application Status": new_status.value,
        "Recruiter Notes": (record.recruiter_notes + "\n" if record.recruiter_notes else "") + req.note,
    })

    return {"status": "success", "new_status": new_status.value}


@app.get("/stats")
async def stats():
    """Pipeline statistics."""
    repo = get_repository()
    records = repo.list_all()

    total = len(records)
    shortlisted = sum(1 for r in records if r.application_status == ApplicationStatus.SHORTLISTED.value)
    review = sum(1 for r in records if r.application_status == ApplicationStatus.MANUAL_REVIEW.value)
    rejected = sum(1 for r in records if r.application_status == ApplicationStatus.REJECTED.value)
    scheduled = sum(1 for r in records if r.application_status == ApplicationStatus.INTERVIEW_SCHEDULED.value)
    avg_score = sum(r.match_score for r in records) / total if total else 0

    return {
        "total_candidates": total,
        "shortlisted": shortlisted,
        "manual_review": review,
        "rejected": rejected,
        "interview_scheduled": scheduled,
        "average_match_score": round(avg_score, 1),
        "cache_backend": type(get_cache()).__name__,
    }


# ------------------------------------------------------------------
# n8n Webhook — entry point for resume processing pipeline
# ------------------------------------------------------------------
@app.post("/webhook/process_resume")
async def webhook_process_resume(
    file: UploadFile = File(...),
    jd_text: str = Form(...),
):
    """
    Webhook for n8n: receives resume + JD, runs full AI pipeline.
    Same as /match_resume but with webhook semantics (for n8n integration).
    """
    logger.event("webhook_call", endpoint="/webhook/process_resume", filename=file.filename)
    return await match_resume(file, jd_text)
