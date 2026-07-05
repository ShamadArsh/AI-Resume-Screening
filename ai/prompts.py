# ============================================================
# ai/prompts.py — Prompt Engineering for Gemini
# ============================================================
# Carefully engineered prompts for:
#   1. Structured resume extraction
#   2. Job-description matching / scoring
# ============================================================

from __future__ import annotations

# ------------------------------------------------------------------
# 1. Resume Extraction Prompt
# ------------------------------------------------------------------
RESUME_EXTRACTION_PROMPT = """\
You are an expert ATS (Applicant Tracking System) resume parser.

Given the raw text of a candidate's resume, extract structured \
information and return ONLY a valid JSON object with these exact keys:

{{
  "name": "Full name of the candidate",
  "email": "Primary email address",
  "phone": "Phone number with country code",
  "experience": "Total years of professional experience (number, e.g. 5)",
  "education": [
    {{"degree": "Degree name", "institution": "School/University", "year": "Graduation year"}}
  ],
  "skills": ["List of technical and soft skills"],
  "certifications": ["List of certifications"],
  "projects": [
    {{"name": "Project name", "description": "Brief description"}}
  ],
  "languages": ["Languages spoken"],
  "current_company": "Current employer name, or null",
  "current_role": "Current job title, or null"
}}

Rules:
- If a field is not found in the resume, use null for strings, [] for lists.
- Do NOT include any text before or after the JSON.
- Do NOT wrap in markdown code fences.
- Return ONLY the JSON object.

Resume Text:
\"\"\"
{resume_text}
\"\"\"
"""

# ------------------------------------------------------------------
# 2. JD Matching Prompt
# ------------------------------------------------------------------
JD_MATCH_PROMPT = """\
You are an expert technical recruiter evaluating a candidate against \
a job description.

Given:
1. The structured candidate data (JSON)
2. The job description text

Return ONLY a valid JSON object with these exact keys:

{{
  "match_score": <integer 0-100>,
  "matching_skills": ["Skills the candidate has that the JD requires"],
  "missing_skills": ["Skills the JD requires that the candidate lacks"],
  "relevant_experience": "Summary of experience relevant to the role",
  "ai_summary": "2-3 sentence assessment of the candidate's fit",
  "hiring_recommendation": "Strongly Recommended | Recommended | Borderline | Not Recommended"
}}

Scoring guide:
- 90-100: Near-perfect match on skills and experience
- 75-89:  Strong match, minor gaps
- 60-74:  Partial match, some gaps
- 40-59:  Weak match, significant gaps
- 0-39:   Poor match

Rules:
- match_score must be an integer between 0 and 100.
- Do NOT include any text before or after the JSON.
- Do NOT wrap in markdown code fences.
- Return ONLY the JSON object.

Candidate Data:
{candidate_json}

Job Description:
\"\"\"
{jd_text}
\"\"\"
"""

# ------------------------------------------------------------------
# 3. AI Summary refinement (optional, for recruiter display)
# ------------------------------------------------------------------
SUMMARY_REFINE_PROMPT = """\
Refine the following candidate assessment into a concise, professional \
paragraph (max 100 words) suitable for display to a recruiter. \
Return only the paragraph text, no JSON.

Assessment:
{assessment}
"""
