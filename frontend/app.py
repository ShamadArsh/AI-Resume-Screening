# ============================================================
# frontend/app.py — Streamlit Recruiter Dashboard
# ============================================================
# Modern recruiter dashboard for the AI Resume Screening
# Platform. Connects to the FastAPI backend.
# ============================================================

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import requests
import streamlit as st

# ------------------------------------------------------------------
# Configuration — detect backend URL automatically
# ------------------------------------------------------------------
def _detect_api_url() -> str:
    """Detect the correct API URL based on environment."""
    # Explicit override
    if os.environ.get("API_URL"):
        return os.environ["API_URL"]
    # Docker Compose: backend is a service name
    if os.environ.get("DOCKER_ENV"):
        return "http://backend:8000"
    # Check if we have a public-facing base domain (behind Caddy proxy)
    base_domain = os.environ.get("DOMAIN", "")
    if base_domain:
        return f"https://{base_domain}/api"
    # Local development
    return "http://localhost:8000"


API_URL = _detect_api_url()

# Add workspace root to sys.path so we can import backend directly
# (for fallback when API is unreachable)
WORKSPACE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE))

# ------------------------------------------------------------------
# Page config
# ------------------------------------------------------------------
st.set_page_config(
    page_title="AI Resume Screening",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a73e8, #4285f4);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 1.5rem;
    }
    .main-header h1 { margin: 0; font-size: 1.8rem; }
    .main-header p { margin: 0.3rem 0 0; opacity: 0.9; }
    .metric-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        border: 1px solid #dadce0;
        text-align: center;
    }
    .score-badge {
        display: inline-block;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: bold;
        font-size: 1.1rem;
    }
    .stButton > button {
        border-radius: 6px;
        font-weight: 500;
    }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------
# API helper
# ------------------------------------------------------------------
def api_get(path: str) -> dict | None:
    try:
        resp = requests.get(f"{API_URL}{path}", timeout=30)
        if resp.status_code == 200:
            return resp.json()
        st.error(f"API error {resp.status_code}: {resp.text[:200]}")
        return None
    except requests.exceptions.ConnectionError:
        st.warning(f"⚠️ Backend at {API_URL} is not reachable. Start it with: `uvicorn backend.api:app --reload`")
        return None
    except Exception as exc:
        st.error(f"Request failed: {exc}")
        return None


def api_post(path: str, files=None, data=None) -> dict | None:
    try:
        resp = requests.post(f"{API_URL}{path}", files=files, data=data, timeout=120)
        if resp.status_code == 200:
            return resp.json()
        st.error(f"API error {resp.status_code}: {resp.text[:300]}")
        return None
    except requests.exceptions.ConnectionError:
        st.warning(f"⚠️ Backend at {API_URL} is not reachable.")
        return None
    except Exception as exc:
        st.error(f"Request failed: {exc}")
        return None


def api_put(path: str, json_data=None) -> dict | None:
    try:
        resp = requests.put(f"{API_URL}{path}", json=json_data, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        st.error(f"API error {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as exc:
        st.error(f"Request failed: {exc}")
        return None


def api_post_json(path: str, json_data: dict) -> dict | None:
    """POST with JSON body."""
    try:
        resp = requests.post(f"{API_URL}{path}", json=json_data, timeout=30)
        if resp.status_code == 200:
            return resp.json()
        st.error(f"API error {resp.status_code}: {resp.text[:200]}")
        return None
    except Exception as exc:
        st.error(f"Request failed: {exc}")
        return None


# ------------------------------------------------------------------
# Render helpers (must be defined before page logic uses them)
# ------------------------------------------------------------------
def _render_score(score: int):
    """Render a color-coded match score."""
    if score >= 80:
        color = "#34a853"
        label = "Shortlisted"
    elif score >= 60:
        color = "#fbbc04"
        label = "Manual Review"
    else:
        color = "#ea4335"
        label = "Rejected"

    st.markdown(
        f"""
        <div style="text-align: center; margin: 1rem 0;">
            <div class="score-badge" style="background: {color}; color: white;">
                Match Score: {score}/100 — {label}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _status_color(status: str) -> str:
    colors = {
        "Shortlisted": "#34a853",
        "Manual Review": "#fbbc04",
        "Rejected": "#ea4335",
        "Interview Scheduled": "#1a73e8",
    }
    return colors.get(status, "#808080")


def _render_candidate_row(cand: dict):
    """Render a compact candidate row with expandable details."""
    score = cand.get("match_score", 0)
    status = cand.get("application_status", "Unknown")
    color = _status_color(status)

    with st.container():
        cols = st.columns([3, 2, 2, 1])
        cols[0].markdown(f"**{cand.get('candidate_name', 'Unknown')}**")
        cols[1].write(cand.get("email", ""))
        cols[2].markdown(f"`{status}`")
        cols[3].markdown(f"**{score}**/100")

        st.markdown(
            f'<div style="height: 2px; background: {color}; margin: 0 0 0.8rem; border-radius: 1px;"></div>',
            unsafe_allow_html=True,
        )


def _render_candidate_detail(cand: dict):
    """Render full candidate detail with actions."""
    score = cand.get("match_score", 0)
    status = cand.get("application_status", "Unknown")

    _render_score(score)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Candidate Info")
        st.write(f"**Name:** {cand.get('candidate_name', 'N/A')}")
        st.write(f"**Email:** {cand.get('email', 'N/A')}")
        st.write(f"**Phone:** {cand.get('phone', 'N/A')}")
        st.write(f"**Experience:** {cand.get('experience', 'N/A')} years")
        st.write(f"**Current Role:** {cand.get('current_role', 'N/A')}")

        st.subheader("Skills")
        skills = cand.get("skills", [])
        if isinstance(skills, str):
            skills = skills.split(", ")
        st.write(", ".join(skills) if skills else "N/A")

    with col2:
        st.subheader("Match Analysis")
        st.write(f"**Status:** `{status}`")
        st.write(f"**Recommendation:** {cand.get('recommendation', 'N/A')}")
        st.write(f"**Relevant Experience:** {cand.get('relevant_experience', 'N/A')}")

        st.markdown("**✅ Matching Skills:**")
        for s in cand.get("matching_skills", []):
            st.markdown(f"  - {s}")

        st.markdown("**❌ Missing Skills:**")
        for s in cand.get("missing_skills", []):
            st.markdown(f"  - {s}")

    st.markdown("---")
    st.subheader("🤖 AI Summary")
    st.info(cand.get("ai_summary", "No summary available."))

    # --- Recruiter Actions ---
    st.markdown("---")
    st.subheader("📋 Recruiter Actions")

    col_act1, col_act2 = st.columns(2)

    with col_act1:
        st.markdown("**Override Status**")
        new_status = st.selectbox(
            "New Status",
            ["Shortlisted", "Manual Review", "Rejected", "Interview Scheduled"],
            key="override_status",
        )
        note = st.text_input("Note (optional)", key="override_note")
        if st.button("Override Status", key="btn_override"):
            result = api_put(
                f"/candidate/{cand.get('id')}/override",
                json_data={"new_status": new_status, "note": note, "recruiter": "recruiter"},
            )
            if result:
                st.success(f"Status updated to: {result.get('new_status')}")

    with col_act2:
        st.markdown("**Schedule Interview**")
        interview_date = st.date_input("Interview Date")
        interview_time = st.time_input("Interview Time")
        if st.button("📅 Schedule Interview", key="btn_schedule", type="primary"):
            from datetime import datetime as dt
            start_dt = dt.combine(interview_date, interview_time).isoformat()
            result = api_post_json(
                "/schedule_interview",
                {"candidate_id": cand.get("id"), "date": start_dt},
            )
            if result and result.get("status") == "success":
                event = result.get("event", {})
                st.success("✅ Interview scheduled!")
                st.write(f"**Event ID:** {event.get('event_id', '')}")
                st.write(f"**Meeting Link:** {event.get('meeting_link', '')}")
                if event.get("mock"):
                    st.caption("⚠️ Running in mock mode — add Google OAuth creds to .env for real calendar events.")


# ------------------------------------------------------------------
# Header
# ------------------------------------------------------------------
st.markdown("""
<div class="main-header">
    <h1>🤖 AI Resume Screening & Interview Scheduling</h1>
    <p>Upload resumes, get AI-powered match scores, and schedule interviews automatically.</p>
</div>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["📊 Dashboard", "📤 Upload & Match", "👥 Candidates", "🔍 Candidate Detail"])

# Backend health in sidebar
health = api_get("/health")
if health:
    st.sidebar.success("✅ Backend Online")
    with st.sidebar.expander("Service Status"):
        cfg = health.get("config", {})
        st.write(f"**Gemini:** {'✅' if cfg.get('gemini_configured') else '❌'}")
        st.write(f"**Airtable:** {'✅' if cfg.get('airtable_configured') else '📦 Mock'}")
        st.write(f"**Redis:** {'✅' if 'redis' in str(cfg.get('redis_url', '')) else '💾 Memory'}")
        st.write(f"**Google OAuth:** {'✅' if cfg.get('google_oauth_configured') else '🔄 Mock'}")
else:
    st.sidebar.error("❌ Backend Offline")

st.sidebar.markdown("---")
st.sidebar.caption(f"API: `{API_URL}`")


# ------------------------------------------------------------------
# Page: Dashboard
# ------------------------------------------------------------------
if page == "📊 Dashboard":
    st.header("📊 Pipeline Dashboard")

    stats = api_get("/stats")
    if stats:
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Candidates", stats.get("total_candidates", 0))
        col2.metric("Shortlisted", stats.get("shortlisted", 0))
        col3.metric("Manual Review", stats.get("manual_review", 0))
        col4.metric("Avg Match Score", f"{stats.get('average_match_score', 0)}")

        col5, col6, _, _ = st.columns(4)
        col5.metric("Rejected", stats.get("rejected", 0))
        col6.metric("Interview Scheduled", stats.get("interview_scheduled", 0))

        st.markdown("---")

        # Pipeline visualization
        st.subheader("📋 Recent Candidates")
        candidates_data = api_get("/candidates")
        if candidates_data and candidates_data.get("candidates"):
            for cand in reversed(candidates_data["candidates"][-10:]):
                _render_candidate_row(cand)
        else:
            st.info("No candidates yet. Upload a resume to get started!")

    else:
        st.warning("Backend offline. Start the FastAPI server to see stats.")


# ------------------------------------------------------------------
# Page: Upload & Match
# ------------------------------------------------------------------
elif page == "📤 Upload & Match":
    st.header("📤 Upload Resume & Match Against JD")

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Resume")
        resume_file = st.file_uploader(
            "Upload Resume (PDF / DOCX)",
            type=["pdf", "docx"],
            help="Max 10 MB. PDF and DOCX supported.",
        )
        if resume_file:
            st.success(f"Loaded: {resume_file.name} ({resume_file.size:,} bytes)")

    with col_right:
        st.subheader("Job Description")
        jd_text = st.text_area(
            "Paste Job Description",
            height=250,
            placeholder="Paste the full job description here...",
        )

    st.markdown("---")

    if st.button("🚀 Parse & Match", type="primary", use_container_width=True):
        if not resume_file:
            st.error("Please upload a resume first.")
        elif not jd_text.strip():
            st.error("Please paste a job description.")
        else:
            with st.spinner("Processing... This calls Gemini 2.5 Flash and may take 10-20 seconds."):
                files = {"file": (resume_file.name, resume_file.getvalue(), "application/octet-stream")}
                data = {"jd_text": jd_text}
                result = api_post("/match_resume", files=files, data=data)

            if result and result.get("status") == "success":
                cand = result["candidate"]
                st.success(f"✅ Processed: {cand.get('candidate_name', 'Unknown')}")

                # Score visualization
                score = cand.get("match_score", 0)
                _render_score(score)

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**✅ Matching Skills:**")
                    matching = cand.get("matching_skills", [])
                    if matching:
                        for s in matching:
                            st.markdown(f"- {s}")
                    else:
                        st.write("_None_")

                with col2:
                    st.markdown("**❌ Missing Skills:**")
                    missing = cand.get("missing_skills", [])
                    if missing:
                        for s in missing:
                            st.markdown(f"- {s}")
                    else:
                        st.write("_None_")

                st.markdown("---")
                st.subheader("🤖 AI Summary")
                st.info(cand.get("ai_summary", "No summary available."))
                st.write(f"**Recommendation:** {cand.get('recommendation', 'N/A')}")
                st.write(f"**Status:** `{cand.get('application_status', 'N/A')}`")
                st.write(f"**Candidate ID:** `{cand.get('id', '')}`")

                # Store ID in session for other pages
                st.session_state["last_candidate_id"] = cand.get("id")
            else:
                st.error("Processing failed. Check the backend logs.")


# ------------------------------------------------------------------
# Page: Candidates List
# ------------------------------------------------------------------
elif page == "👥 Candidates":
    st.header("👥 All Candidates")

    candidates_data = api_get("/candidates")
    if candidates_data and candidates_data.get("candidates"):
        candidates = candidates_data["candidates"]

        # Filter
        status_filter = st.selectbox(
            "Filter by Status",
            ["All", "Shortlisted", "Manual Review", "Rejected", "Interview Scheduled"],
        )
        if status_filter != "All":
            candidates = [c for c in candidates if c.get("application_status") == status_filter]

        st.write(f"Showing **{len(candidates)}** candidate(s)")

        for cand in reversed(candidates):
            _render_candidate_row(cand)
    else:
        st.info("No candidates yet. Upload resumes to populate this list.")


# ------------------------------------------------------------------
# Page: Candidate Detail
# ------------------------------------------------------------------
elif page == "🔍 Candidate Detail":
    st.header("🔍 Candidate Detail")

    candidate_id = st.text_input(
        "Enter Candidate ID",
        value=st.session_state.get("last_candidate_id", ""),
        placeholder="e.g. recXXXXXXXXXXXX",
    )

    if candidate_id and st.button("Load Candidate"):
        cand = api_get(f"/candidate/{candidate_id}")
        if cand:
            st.session_state["current_candidate"] = cand

    cand = st.session_state.get("current_candidate")
    if cand:
        _render_candidate_detail(cand)
