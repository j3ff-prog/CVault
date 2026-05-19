"""
services/gemini_service.py
Handles all calls to Google Gemini 2.5 Flash.

Free tier limits (as of 2025):
  - 1,500 requests/day
  - 1,000,000 tokens/minute
  - No credit card needed

Get your API key at: https://aistudio.google.com/app/apikey
"""

import os
import json
from google import genai
from dotenv import load_dotenv

load_dotenv()

_api_key = os.getenv("GEMINI_API_KEY", "")
if not _api_key:
    raise EnvironmentError(
        "GEMINI_API_KEY is not set. Add it to your environment variables."
    )

client = genai.Client(api_key=_api_key)
MODEL = "gemini-2.5-flash"

PROMPT_TEMPLATE = """You are an elite CV writer and career strategist with 15 years of experience placing candidates at top companies across East Africa and globally. You write CVs and cover letters that actually get interviews — not generic templates.

STRICT RULES:
- Never invent jobs, qualifications, or skills that are not in the original CV
- Never use clichés like "dynamic", "passionate", "results-driven", "synergy", "leverage", "spearhead"
- Never start bullet points with weak verbs like "Helped", "Assisted", "Worked on"
- Every bullet point must start with a strong action verb and include a specific outcome or context
- The cover letter must sound like a real person wrote it — specific, direct, no filler sentences
- Do not pad. If the person only has 2 jobs, only write 2 jobs. Do not repeat information.
- The professional summary must be 2-3 tight sentences — no fluff
- Extract the exact date on the user's system for the cover letter date — use today's date

YOUR TASK:
1. Read the candidate's CV carefully — extract their real experience, education, and skills
2. Read the job description — extract the exact keywords, required skills, and what the employer cares about most
3. Rewrite the CV to speak directly to this job:
   - Reorder and reword bullet points to surface the most relevant experience first
   - Use keywords from the JD naturally — not forced
   - Quantify achievements wherever the original CV has any hint of scale (e.g. "managed X customers" → "Managed a portfolio of X+ customer accounts")
   - Make every bullet point a mini achievement, not a task description
4. Write a cover letter that:
   - Opens with a specific, genuine hook — reference the company or role directly if possible
   - Paragraph 2: connects their strongest relevant experience to the top 2-3 JD requirements — be specific
   - Paragraph 3: highlights one concrete achievement relevant to the role — something that proves they can do the job
   - Paragraph 4: short, confident close — no grovelling, no "I would be honoured"
   - Tone: professional but human — like a confident person writing to someone they respect

CV FORMATTING STANDARDS:
- Contact info: Phone | Email | Location (one line, pipe-separated)
- Section headers: PROFESSIONAL SUMMARY, WORK EXPERIENCE, EDUCATION, SKILLS
- Job entries: Job Title bold, Company · Period on next line, then 3-4 tight bullet points
- Skills: grouped logically, not a random list
- No "References available on request" — waste of space

Return ONLY a valid JSON object. No markdown. No code fences. Nothing before or after the JSON:

{{
  "matchScore": <integer 50-95 — be honest, not always high>,
  "matchedKeywords": [<6-8 exact keyword strings pulled from the JD that appear in the tailored CV>],
  "scoreDescription": "<one honest sentence — e.g. 'Strong match on customer service skills; gap in technical certifications'>",
  "candidateName": "<full name from CV — properly capitalised>",
  "contactInfo": "<phone | email | city, country>",
  "tailoredCV": {{
    "summary": "<2-3 sentences. Start with their role/level, then their strongest relevant skill, then what they bring to this specific role. No buzzwords.>",
    "experience": [
      {{
        "title": "<exact job title>",
        "company": "<company name>",
        "period": "<Month Year – Month Year or Month Year – Present>",
        "bullets": [
          "<Strong action verb + what they did + specific context or outcome>",
          "<Strong action verb + what they did + specific context or outcome>",
          "<Strong action verb + what they did + specific context or outcome>"
        ]
      }}
    ],
    "education": [
      {{
        "degree": "<full qualification name>",
        "institution": "<institution name>",
        "year": "<graduation year or expected year>"
      }}
    ],
    "skills": [
      "<skill>", "<skill>", "<skill>", "<skill>", "<skill>", "<skill>", "<skill>", "<skill>"
    ]
  }},
  "coverLetter": "<Cover letter as a single string. Use \\n\\n to separate paragraphs. Format:\\n\\n[Today's date — e.g. 19 May 2026]\\n\\nDear [Hiring Manager's name if visible in JD, otherwise 'Hiring Manager'],\\n\\n[Paragraph 1 — specific opening hook, name the role and why you are applying. 2-3 sentences max.]\\n\\n[Paragraph 2 — connect your strongest relevant experience to the top JD requirements. Be specific. No vague claims.]\\n\\n[Paragraph 3 — one concrete achievement that proves you can do this job. If possible include a number or result.]\\n\\n[Paragraph 4 — confident close. Express availability for interview. Thank them briefly. 2 sentences.]\\n\\nYours sincerely,\\n[Candidate full name]>"
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
        RuntimeError — on Gemini API errors
    """
    if not cv_text or not cv_text.strip():
        raise ValueError("CV text cannot be empty.")
    if not job_description or not job_description.strip():
        raise ValueError("Job description cannot be empty.")

    prompt = PROMPT_TEMPLATE.format(
        cv_text=cv_text.strip(),
        job_description=job_description.strip()
    )

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

    # Strip accidental markdown code fences
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    # Isolate the JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(
            f"Gemini response did not contain valid JSON. "
            f"Preview: {raw[:300]}"
        )
    cleaned = cleaned[start:end + 1]

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Could not parse Gemini response as JSON. "
            f"Error: {e}. Preview: {raw[:300]}"
        )

    # Validate required fields
    for key in ["matchScore", "tailoredCV", "coverLetter"]:
        if key not in parsed:
            raise ValueError(f"Gemini response missing field: '{key}'")

    # Sanitise matchScore
    try:
        parsed["matchScore"] = max(0, min(100, int(parsed["matchScore"])))
    except (TypeError, ValueError):
        parsed["matchScore"] = 75

    if not isinstance(parsed.get("matchedKeywords"), list):
        parsed["matchedKeywords"] = []

    return parsed