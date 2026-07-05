# 🤖 AI Resume Screening & Interview Scheduling Platform

> A production-ready, AI-powered recruitment workflow that parses PDF/DOCX resumes, extracts structured candidate data using **Gemini 2.5 Flash**, matches candidates against a Job Description, calculates an AI Match Score, shortlists automatically, stores data in **Airtable**, and delegates all interview scheduling (**Google Calendar + Meet + Gmail**) to **n8n** via webhook.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture Diagram](#architecture-diagram)
- [Tech Stack](#tech-stack)
- [Features](#features)
- [Project Structure](#project-structure)
- [Setup Instructions](#setup-instructions)
- [Environment Variables](#environment-variables)
- [API Documentation](#api-documentation)
- [n8n Workflow Explanation](#n8n-workflow-explanation)
- [Workflow Walkthrough](#workflow-walkthrough)
- [Business Rules](#business-rules)
- [Caching Strategy](#caching-strategy)
- [Graceful Degradation](#graceful-degradation)
- [Deployment Guide](#deployment-guide)
- [Testing](#testing)
- [Security](#security)
- [Error Handling](#error-handling)

---

## Overview

This platform automates the end-to-end recruitment screening pipeline using a **clean separation of concerns**:

- **FastAPI** handles ONLY AI-related work: resume parsing, Gemini extraction, JD matching, ATS scoring, and candidate storage.
- **n8n** handles ALL workflow automation: Google Calendar event creation, Google Meet link generation, Gmail interview invitations, and Airtable status updates.

```
Recruiter uploads resume (Streamlit)
    → FastAPI: Parse → Gemini Analysis → ATS Matching → Airtable Storage
    → FastAPI: POST candidate JSON to n8n webhook
    → n8n: IF score >= 80 → Google Calendar (Meet) → Gmail → Update Airtable
    → n8n: IF score < 80  → Update Airtable → End
```

The system is **modular**, **scalable**, and **production-ready**. Every external dependency (Gemini, Airtable, Redis, n8n) includes graceful fallback behavior, so the application runs in full or partial configurations.

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                          │
│  ┌────────────────────────────────────────────┐                    │
│  │          Streamlit Dashboard               │                    │
│  │  Upload Resume → View Results → History    │                    │
│  └────────────────────┬───────────────────────┘                    │
└───────────────────────┼─────────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────────┐
│                      FASTAPI — AI LAYER ONLY                        │
│                                                                     │
│  ┌────────────┐  ┌─────────────┐  ┌──────────┐  ┌───────────┐      │
│  │ PDF Parser │  │ DOCX Parser │  │  Gemini  │  │ JD Matcher│      │
│  │ (PyMuPDF + │  │ (python-   │  │ 2.5 Flash│  │ (Scoring) │      │
│  │  pdfplumber│  │  docx)     │  │          │  │           │      │
│  └────────────┘  └─────────────┘  └──────────┘  └───────────┘      │
│                        │                                            │
│         ┌──────────────▼──────────────┐                             │
│         │   Business Rule Engine      │                             │
│         │  ≥80 Shortlist | 60-79 Review│ <60 Reject                │
│         └──────────────┬──────────────┘                             │
│                        │                                            │
│         ┌──────────────▼──────────────┐  ┌──────────────┐          │
│         │       Airtable (Store)      │  │    Redis     │          │
│         │     Candidate Repository    │  │   (Cache)    │          │
│         └──────────────┬──────────────┘  └──────────────┘          │
│                        │                                            │
│         ┌──────────────▼──────────────┐                             │
│         │   n8n Webhook (POST JSON)   │  ← FastAPI delegates here   │
│         │   backend/n8n_webhook.py    │                             │
│         └──────────────┬──────────────┘                             │
└────────────────────────┼────────────────────────────────────────────┘
                         │
                         │  POST /webhook/interview
                         │  {candidate_name, email, phone, match_score, ...}
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    n8n — WORKFLOW AUTOMATION                        │
│                                                                     │
│  ┌──────────────┐                                                   │
│  │Webhook Trigger│                                                  │
│  │POST /interview│                                                  │
│  └──────┬───────┘                                                   │
│         │                                                           │
│  ┌──────▼───────┐                                                   │
│  │  IF score ≥ 80?                                                 │
│  └──┬───────┬───┘                                                   │
│     │YES    │NO                                                    │
│     ▼       ▼                                                      │
│  ┌────────┐ ┌──────────┐                                          │
│  │Calendar│ │Update Air│                                          │
│  │+ Meet  │ │table     │                                          │
│  └───┬────┘ └────┬─────┘                                          │
│      ▼          ▼                                                  │
│  ┌────────┐ ┌──────────┐                                          │
│  │ Gmail  │ │   End    │                                          │
│  │Invite  │ └──────────┘                                          │
│  └───┬────┘                                                        │
│      ▼                                                             │
│  ┌────────┐                                                        │
│  │Update  │                                                        │
│  │Airtable│                                                        │
│  └───┬────┘                                                        │
│      ▼                                                             │
│  ┌────────┐                                                        │
│  │Success │                                                        │
│  └────────┘                                                        │
└─────────────────────────────────────────────────────────────────────┘
```

**Key architectural principle:** FastAPI is responsible for intelligence (AI). n8n is responsible for actions (scheduling, email, calendar). They communicate through a typed webhook contract.


---

## Tech Stack

| Component            | Technology                        | Purpose                              |
|---------------------|-----------------------------------|--------------------------------------|
| **Backend**          | FastAPI (Python 3.13)            | REST API, AI pipeline (parse/match/score/store) |
| **Workflow**         | n8n                               | Workflow automation: Calendar, Gmail, Airtable |
| **LLM**              | Gemini 2.5 Flash (`google-genai`) | Resume extraction, JD matching       |
| **Resume Parsing**   | pdfplumber + PyMuPDF + python-docx| PDF/DOCX text extraction             |
| **Database**         | Airtable (`pyairtable`)           | Candidate data storage               |
| **Cache**            | Redis                             | Cache AI responses, avoid recompute  |
| **Email**            | Gmail API                         | Interview invitations                |
| **Calendar**         | Google Calendar API               | Interview scheduling + Meet links    |
| **Frontend**         | Streamlit                         | Recruiter dashboard                  |
| **Deployment**       | Docker + Docker Compose           | Containerized deployment             |
| **Embeddings (Bonus)**| sentence-transformers (BGE)      | Semantic similarity                  |
| **Vector Store (Bonus)**| ChromaDB                       | Vector search                        |

---

## Features

### Resume Parsing
Extracts structured data from resumes:
- ✅ Candidate Name, Email, Phone
- ✅ Experience (years)
- ✅ Education (degree, institution, year)
- ✅ Skills (list)
- ✅ Certifications
- ✅ Projects
- ✅ Languages
- ✅ Current Company & Role

### Job Description Matching
Returns:
- ✅ Match Score (0-100)
- ✅ Matching Skills
- ✅ Missing Skills
- ✅ Relevant Experience
- ✅ AI Summary
- ✅ Hiring Recommendation

### Business Rules & Overrides
- ✅ Automatic shortlisting based on configurable thresholds
- ✅ Recruiter can override any AI decision

### Caching
- ✅ SHA-256 hash of resume/JD text → cache key
- ✅ Cache hits skip Gemini calls entirely
- ✅ In-memory LRU fallback when Redis is unavailable

### Email Templates (Configurable)
- ✅ Application Received
- ✅ Shortlisted
- ✅ Interview Invitation
- ✅ Rejected

### Structured Logging
Logs all business events: Resume Upload, AI Request, Cache Hit/Miss, Database Write, Interview Scheduled, Errors.

---

## Project Structure

```
.
├── backend/
│   ├── __init__.py
│   ├── api.py              # FastAPI app — all REST endpoints
│   └── config.py           # Centralized config (pydantic-settings)
├── parser/
│   ├── __init__.py         # Unified entry: parse_resume_file/bytes
│   ├── pdf_parser.py       # PDF extraction (PyMuPDF + pdfplumber)
│   └── docx_parser.py      # DOCX extraction (python-docx)
├── ai/
│   ├── __init__.py
│   ├── prompts.py          # Prompt engineering for Gemini
│   ├── resume_parser.py    # Gemini-powered resume extraction
│   ├── jd_matcher.py       # JD matching + scoring
│   └── scoring.py          # Business rule engine + overrides
├── database/
│   ├── __init__.py
│   ├── airtable.py         # Airtable repository (with mock fallback)
│   └── redis_cache.py      # Redis cache (with in-memory fallback)
├── scheduler/
│   ├── __init__.py
│   ├── gmail.py            # Gmail email service (configurable templates)
│   └── google_calendar.py  # Google Calendar interview scheduling
├── utils/
│   ├── __init__.py
│   ├── logger.py           # Structured JSON logging
│   └── validators.py       # File/email/phone/JSON validation
├── frontend/
│   └── app.py              # Streamlit recruiter dashboard
├── workflows/
│   └── n8n_workflow.json   # n8n workflow (importable)
├── tests/
│   ├── test_api.py         # API integration tests
│   ├── test_validators.py  # Validator unit tests
│   ├── test_scoring.py     # Business rule tests
│   ├── test_cache.py       # Cache unit tests
│   ├── test_airtable.py    # Repository unit tests
│   └── test_parsers.py     # Parser tests
├── .env.example            # Copy to .env and fill credentials
├── requirements.txt        # Python dependencies
├── Dockerfile              # Container image definition
├── docker-compose.yml      # Full stack: redis, backend, frontend, n8n
└── README.md               # This file
```

---

## Setup Instructions

### Prerequisites
- Python 3.13+
- Docker & Docker Compose (for containerized deployment)
- API keys for the services you want to use (see [Environment Variables](#environment-variables))

### Option 1: Docker Compose (Recommended)

```bash
# 1. Clone the repository
git clone <repo-url>
cd ai-resume-screening

# 2. Copy environment template
cp .env.example .env

# 3. Fill in your API keys
nano .env

# 4. Start all services
docker-compose up -d

# 5. Access:
#    - Streamlit Dashboard:  http://localhost:8501
#    - FastAPI Docs:         http://localhost:8000/docs
#    - n8n Workflow Editor:  http://localhost:5678
#    - Redis:                localhost:6379
```

### Option 2: Local Development

```bash
# 1. Create virtual environment
python3 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set up environment
cp .env.example .env
# Edit .env with your credentials

# 4. Start Redis (if using Redis caching)
redis-server &

# 5. Start FastAPI backend
uvicorn backend.api:app --reload --port 8000

# 6. In another terminal, start Streamlit
streamlit run frontend/app.py --server.port 8501

# 7. (Optional) Start n8n
npx n8n
```

---

## Environment Variables

All configuration is read from `.env`. Copy `.env.example` and fill in your credentials:

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | ✅ | Google Gemini API key — [Get it here](https://aistudio.google.com/apikey) |
| `GEMINI_MODEL` | No | Default: `gemini-2.5-flash` |
| `AIRTABLE_API_KEY` | ✅ | Airtable Personal Access Token — [Get it here](https://airtable.com/create/tokens) |
| `AIRTABLE_BASE_ID` | ✅ | Base ID from Airtable API docs |
| `AIRTABLE_TABLE_NAME` | No | Default: `Candidates` |
| `REDIS_URL` | No | Default: `redis://localhost:6379/0` |
| `GOOGLE_CLIENT_ID` | ✅* | Google OAuth Client ID |
| `GOOGLE_CLIENT_SECRET` | ✅* | Google OAuth Client Secret |
| `GOOGLE_REFRESH_TOKEN` | ✅* | OAuth refresh token |
| `SHORTLIST_THRESHOLD` | No | Default: 80 |
| `REVIEW_THRESHOLD` | No | Default: 60 |
| `SECRET_KEY` | Yes | App secret key (change in production!) |

> *\* Google OAuth credentials are required for real Gmail/Calendar. Without them, the app runs in mock mode (emails are logged, events are simulated).*

### Airtable Table Schema

Create a table named `Candidates` (or your `AIRTABLE_TABLE_NAME`) with these fields:

| Field Name | Type | Notes |
|---|---|---|
| Candidate Name | Single line text | |
| Email | Email | |
| Phone | Phone number | |
| Experience | Single line text | |
| Skills | Long text | Comma-separated |
| Match Score | Number | 0-100 |
| Matching Skills | Long text | Comma-separated |
| Missing Skills | Long text | Comma-separated |
| AI Summary | Long text | |
| Recommendation | Single line text | |
| Application Status | Single select | Shortlisted, Manual Review, Rejected |
| Recruiter Notes | Long text | |
| Interview Status | Single line text | |
| Interview Date | Date | |
| Interview Link | URL | |
| Resume Text | Long text | |
| Created Time | Created time | |
| Updated Time | Last modified time | |

---

## API Documentation

Interactive docs available at `http://localhost:8000/docs` (Swagger) and `http://localhost:8000/redoc`.

### `POST /parse_resume`
Extract structured data from a resume file using Gemini 2.5 Flash.

```bash
curl -X POST http://localhost:8000/parse_resume \
  -F "file=@resume.pdf"
```

**Response:**
```json
{
  "status": "success",
  "filename": "resume.pdf",
  "candidate": {
    "name": "Jane Smith",
    "email": "jane@email.com",
    "phone": "+1-555-987-6543",
    "experience": "8",
    "skills": ["Python", "FastAPI", "AWS"],
    "education": [{"degree": "MS CS", "institution": "MIT", "year": "2016"}],
    "certifications": ["AWS Solutions Architect"],
    "current_company": "Tech Corp",
    "current_role": "Senior Engineer"
  }
}
```

### `POST /match_resume`
Full pipeline: parse resume + match against JD + score + store + send email.

```bash
curl -X POST http://localhost:8000/match_resume \
  -F "file=@resume.pdf" \
  -F "jd_text=We are hiring a Senior Python Engineer..."
```

### `POST /schedule_interview`
Schedule an interview via Google Calendar and send a Gmail invitation.

```bash
curl -X POST http://localhost:8000/schedule_interview \
  -H "Content-Type: application/json" \
  -d '{"candidate_id": "recXXXXXX", "date": "2025-07-10T09:00:00Z"}'
```

### `GET /candidate/{id}`
Get full candidate details.

### `PUT /candidate/{id}/override`
Recruiter overrides AI status.

```bash
curl -X PUT http://localhost:8000/candidate/recXXX/override \
  -H "Content-Type: application/json" \
  -d '{"new_status": "Shortlisted", "note": "Strong portfolio"}'
```

### `GET /candidates`
List all candidates.

### `GET /health`
Service health check with configuration status.

### `GET /stats`
Pipeline statistics (counts, average score, cache backend).

### `POST /webhook/process_resume`
Webhook endpoint for n8n integration (same as `/match_resume`).

---

## n8n Workflow Explanation

The file `workflows/n8n_workflow.json` contains a complete, importable n8n workflow that handles **all workflow automation** — Google Calendar, Google Meet, Gmail, and Airtable updates — after FastAPI completes its AI analysis.

### Workflow Nodes

1. **Webhook Trigger** (`POST /webhook/interview`) — Receives candidate JSON from FastAPI
2. **Match Score >= 80?** — IF node that branches based on AI match score
3. **Set Interview Slot** — Calculates interview date/time (2 days from now, 10:00 UTC)
4. **Google Calendar** — Creates a 60-minute interview event with Google Meet, adds candidate as attendee
5. **Send Gmail Invitation** — Sends congratulations + interview invitation email with Meet link
6. **Update Airtable (Scheduled)** — Updates candidate status to "Interview Scheduled"
7. **Success** — Workflow completes for shortlisted candidates
8. **Update Airtable (Not Shortlisted)** — Score < 80: updates status (Rejected/Manual Review)
9. **End Workflow** — No interview scheduled for non-shortlisted candidates

### Architecture Flow

```
FastAPI → POST /webhook/interview → n8n Webhook Trigger
                                        │
                                   IF score >= 80?
                                    /         \
                                  YES          NO
                                   │            │
                          Google Calendar   Update Airtable
                          (60min + Meet)         │
                                   │           End
                          Gmail Invitation
                                   │
                          Update Airtable
                                   │
                              Success
```

### Importing the Workflow

1. Open n8n at `http://localhost:5678`
2. Click **Workflows** → **Import from File**
3. Select `workflows/n8n_workflow.json`
4. Configure credentials in n8n:
   - **Google Calendar** — OAuth2 credentials
   - **Gmail** — OAuth2 credentials
   - **Airtable** — API key or OAuth2
5. Set the webhook path to `interview` (should be auto-configured)
6. **Activate** the workflow
7. Ensure `N8N_WEBHOOK_URL=http://localhost:5678/webhook/interview` is set in FastAPI's `.env`

---

## Workflow Walkthrough

### Step-by-Step: From Upload to Interview

1. **Recruiter** uploads a resume in the **Streamlit dashboard**
2. **Streamlit** sends the file to FastAPI's `POST /match_resume`
3. **FastAPI** runs the AI pipeline:
   - Extracts text from the PDF/DOCX (PyMuPDF → pdfplumber fallback)
   - Sends text to **Gemini 2.5 Flash** for structured extraction
   - Matches candidate data against the **Job Description** (Gemini)
   - Calculates **AI Match Score** (0-100)
   - Applies **Business Rules** (≥80 shortlist / 60-79 review / <60 reject)
   - Stores the candidate in **Airtable**
4. **FastAPI** sends candidate JSON to **n8n** via `POST /webhook/interview`
5. **n8n** checks the match score:
   - **≥80 (Shortlisted):**
     - Creates **Google Calendar** event (60 min) with **Google Meet** link
     - Sends **Gmail** congratulations + interview invitation with Meet link
     - Updates **Airtable** status → "Interview Scheduled"
   - **<80 (Review/Rejected):**
     - Updates **Airtable** status only
6. **Recruiter** reviews results in the **Streamlit dashboard**
7. Recruiter can **override** any AI decision

---

## Business Rules

| Match Score | Status | Action |
|-------------|--------|--------|
| ≥ 80 | Shortlisted | Auto-schedule interview |
| 60–79 | Manual Review | Recruiter reviews manually |
| < 60 | Rejected | Rejection email sent |

Thresholds are configurable via `SHORTLIST_THRESHOLD` and `REVIEW_THRESHOLD` in `.env`.

Recruiters can override any status via the dashboard or `PUT /candidate/{id}/override`.

---

## Caching Strategy

The platform uses **Redis** for caching with **SHA-256 hashing** to generate cache keys:

```
cache_key = "resume:" + SHA256(resume_text)        # for resume parsing
cache_key = "resume:" + SHA256(candidate + jd_text) # for JD matching
```

**Behavior:**
- Cache **hit** → returns cached result instantly (no Gemini call)
- Cache **miss** → calls Gemini, stores result with TTL
- TTL: 3600 seconds (1 hour), configurable via `CACHE_TTL`

**Fallback:** If Redis is unavailable, an **in-memory LRU cache** (max 500 entries) takes over automatically — no code changes needed.

---

## Graceful Degradation

The platform is designed to **never crash** when external services are unavailable:

| Service | Without Credentials | Behavior |
|---------|-------------------|----------|
| Gemini | `GEMINI_API_KEY` missing | Returns 503 with clear error message |
| Airtable | Creds missing | Falls back to in-memory mock store |
| Redis | Unreachable | Falls back to in-memory LRU cache |
| Gmail | OAuth missing | Emails are logged (mock mode) |
| Google Calendar | OAuth missing | Generates mock meeting links |

This means the app is **fully functional for demos and testing** even without any external credentials — add them to `.env` to enable the real integrations.

---

## Deployment Guide

### Docker Compose (Production)

```bash
# Build and start all services
docker-compose up -d --build

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f n8n

# Stop all services
docker-compose down

# Stop and remove volumes (fresh start)
docker-compose down -v
```

### Services

| Service | Port | Description |
|---------|------|-------------|
| `backend` | 8000 | FastAPI REST API |
| `frontend` | 8501 | Streamlit dashboard |
| `redis` | 6379 | Redis cache |
| `n8n` | 5678 | n8n workflow editor |

### Health Checks

All services include Docker health checks. Verify with:

```bash
docker-compose ps
```

---

## Testing

```bash
# Run all tests
python3 -m pytest tests/ -v

# Run with coverage
python3 -m pytest tests/ --cov=. --cov-report=term-missing

# Run specific test module
python3 -m pytest tests/test_scoring.py -v
```

### Test Coverage

| Test File | What it Covers |
|-----------|---------------|
| `test_validators.py` | File type validation, size limits, email/phone format, JSON extraction, filename sanitization |
| `test_scoring.py` | Business rules (thresholds), status overrides, edge cases (negative/over-100 scores) |
| `test_cache.py` | Cache set/get/delete, TTL expiry, LRU eviction, key consistency |
| `test_airtable.py` | CandidateRecord creation, dict conversion |
| `test_api.py` | API health, stats, candidate CRUD, error responses |
| `test_parsers.py` | PDF/DOCX parser error handling |

---

## Security

- ✅ All secrets stored in `.env` (never committed)
- ✅ `.env.example` contains no real credentials
- ✅ API keys loaded via environment variables
- ✅ Input validation on all file uploads (type, size)
- ✅ Path traversal prevention in file handling
- ✅ CORS configurable via `ALLOWED_ORIGINS`
- ✅ `SECRET_KEY` must be changed for production

---

## Error Handling

The platform handles errors gracefully with **automatic retries**:

| Error Type | Handling |
|-----------|----------|
| Unsupported file | 400 Bad Request with detail |
| Corrupted PDF | Fallback parser, then 422 |
| Invalid Gemini JSON | JSON repair attempts, then 503 |
| Gemini timeout | Exponential backoff retry (3 attempts) |
| Redis failure | Automatic fallback to memory cache |
| Airtable failure | Automatic fallback to mock store |
| Calendar failure | Mock event generated, error logged |
| Email failure | Error logged, pipeline continues |

Retry logic uses `tenacity` with exponential backoff:
- Min wait: 2 seconds
- Max wait: 30 seconds
- Max attempts: 3 (configurable via `GEMINI_MAX_RETRIES`)

---

## License

This project is part of an AI Engineer technical assessment.

---

## Author

Built as a production-ready AI recruitment platform demonstrating LLM integration, workflow automation, prompt engineering, scalable architecture, REST APIs, Redis caching, and Docker deployment.
