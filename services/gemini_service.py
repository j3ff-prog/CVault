"""
services/gemini_service.py
Handles all calls to Google Gemini 2.5 Flash.

Free tier limits (as of 2025):
  - 1,500 requests/day
  - 1,000,000 tokens/minute
  - No credit card needed

Get your API key at: https://aistudio.google.com/app/apikey

Add this to your .env file:
  GEMINI_API_KEY=your-key-here
"""

import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

# ── Client setup ──────────────────────────────────────────────────────────────
# API key is loaded from .env — never hardcode it here
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))

# ── Model ─────────────────────────────────────────────────────────────────────
# gemini-2.5-flash — fast, free, more than capable for CV tailoring
# gemini-1.5-flash and all gemini-2.0-* / gemini-1.5-* are DEPRECATED — do not use them
MODEL = "gemini-2.5-flash"

# ── Prompt template ───────────────────────────────────────────────────────────
PROMPT_TEMPLATE = """You are CVault, an expert CV writer and career coach specialising in the Kenyan job market.

Your task:
1. Read the candidate's CV carefully.
2. Read the job description. Extract exact keywords, required skills, and qualifications.
3. Rewrite the CV to closely match this specific role — use the JD's exact language, emphasise relevant experience, and make every bullet point results-focused and specific. Do NOT invent experience that is not in the original CV.
4. Write a professional, human-sounding cover letter for this exact role. Four paragraphs:
   (1) Express genuine interest and name the role and company.
   (2) Connect specific experience to the JD's requirements.
   (3) Highlight one key relevant achievement with a number or result where possible.
   (4) Confident call to action.
   Address to Hiring Manager unless a name appears in the JD.

Return ONLY a valid JSON object. No markdown. No code fences. No explanation before or after. Just the raw JSON:

{{
  "matchScore": <integer between 40 and 97>,
  "matchedKeywords": [<list of 5 to 7 exact keyword strings from the job description>],
  "scoreDescription": "<one sentence describing the match quality>",
  "candidateName": "<full name extracted from the CV>",
  "contactInfo": "<phone | email | location — pipe-separated, extracted from CV>",
  "tailoredCV": {{
    "summary": "<2 to 3 sentence professional summary written specifically for this role>",
    "experience": [
      {{
        "title": "<job title>",
        "company": "<company name>",
        "period": "<date range e.g. Jan 2022 – Mar 2024>",
        "bullets": ["<achievement bullet>", "<achievement bullet>", "<achievement bullet>"]
      }}
    ],
    "education": [
      {{ "degree": "<qualification>", "institution": "<school or university>", "year": "<year>" }}
    ],
    "skills": ["<skill>", "<skill>", "<skill>", "<skill>", "<skill>", "<skill>"]
  }},
  "coverLetter": "<full cover letter — 4 paragraphs separated by \\n\\n. Start with today's date on the first line.>"
}}

---

CANDIDATE CV:
{cv_text}

---

JOB DESCRIPTION:
{job_description}
"""


def tailor_cv(cv_text: str, job_description: str) -> dict:
    """
    Send CV and job description to Gemini 2.5 Flash.
    Returns the parsed JSON dict.

    Raises:
        ValueError  — if the response cannot be parsed as valid JSON
        RuntimeError — on Gemini API errors (network, auth, quota etc.)
    """
    if not cv_text or not cv_text.strip():
        raise ValueError("CV text cannot be empty.")

    if not job_description or not job_description.strip():
        raise ValueError("Job description cannot be empty.")

    prompt = PROMPT_TEMPLATE.format(
        cv_text=cv_text.strip(),
        job_description=job_description.strip()
    )

    # ── Call Gemini 2.5 Flash ─────────────────────────────────────────────────
    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt
        )
    except Exception as e:
        raise RuntimeError(f"Gemini API error: {str(e)}")

    raw = response.text or ""

    if not raw.strip():
        raise ValueError("Gemini returned an empty response. Please try again.")

    # ── Clean the response ────────────────────────────────────────────────────
    # Strip any accidental markdown code fences Gemini sometimes adds
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    # Find the first { and last } to isolate the JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(
            f"Gemini response did not contain valid JSON. "
            f"Raw response preview: {raw[:300]}"
        )
    cleaned = cleaned[start:end + 1]

    # ── Parse JSON ────────────────────────────────────────────────────────────
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Could not parse Gemini response as JSON. "
            f"Error: {e}. Raw response preview: {raw[:300]}"
        )

    # ── Validate required fields ──────────────────────────────────────────────
    required_fields = ["matchScore", "tailoredCV", "coverLetter"]
    for key in required_fields:
        if key not in parsed:
            raise ValueError(
                f"Gemini response is missing required field: '{key}'. "
                f"Got keys: {list(parsed.keys())}"
            )

    # ── Sanitise matchScore ───────────────────────────────────────────────────
    # Make sure it is an integer between 0 and 100
    try:
        parsed["matchScore"] = max(0, min(100, int(parsed["matchScore"])))
    except (TypeError, ValueError):
        parsed["matchScore"] = 75  # safe fallback

    # ── Ensure matchedKeywords is always a list ───────────────────────────────
    if not isinstance(parsed.get("matchedKeywords"), list):
        parsed["matchedKeywords"] = []

    return parsed