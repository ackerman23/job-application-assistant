"""AI-only job description extraction."""

import re

from app.core.config import JD_MODEL, OPENAI_API_KEY
from app.models.schemas import JobAnalysis
from app.services.llm import complete_json


EXTRACTION_PROMPT = """Carefully analyze only the supplied job description and return one JSON object matching the supplied JobAnalysis schema.

Extract the role, company, location, employment details, responsibilities, required skills, preferred skills, technical skills, soft skills, engineering domains, education and language requirements, tools and technologies, implicit technical requirements, and keywords. Keep required, preferred, and implicit categories distinct. Do not add anything that is not stated or clearly required by the job description. Do not assess the candidate. Set job_language to French when the job description is predominantly written in French; otherwise set it to English.

Technical focus is essential: technical_skills, tools_and_technologies, domain_keywords, required_skills, preferred_skills, and implicit_requirements must contain concise named technical capabilities, engineering domains, programming languages, platforms, tools, standards, or methods only. Do not put communication, teamwork, leadership, interpersonal skills, stakeholder management, organization, time management, personality traits, or generic behavior requirements into those technical fields. If relevant, put generic interpersonal requirements only in soft_skills; the application may exclude those from CV selection.

Quality rules: use atomic canonical names, one concept per entry ("Python" and "C++", never "Python/C++ programming"). Split slash- or comma-joined lists into separate entries. Keep the exact spelling used in the posting, and put a well-known acronym in the same entry only when the posting itself gives it. Do not repeat a term across required_skills and preferred_skills; if the posting says it is both, keep it required. Put a technology in required_skills when it is listed as required, expected, or central to the responsibilities, and in preferred_skills only when the posting says nice to have, plus, or advantage. Capture tools and frameworks named inside responsibility sentences, not only inside requirement lists. Do not list degree names, language fluency, or years of experience as skills.

Prefer specific named terms over sentences. Preserve whether a requirement is mandatory or preferred when the text provides that distinction. Include only requirements supported by the supplied text. Set analysis_method to AI-assisted and analysis_warning to an empty string."""


SKILL_FIELDS = (
    "required_skills", "preferred_skills", "technical_skills", "tools_and_technologies", "domain_keywords",
)
SPLIT_PATTERN = re.compile(r"\s*(?:/|,|;|\s+&\s+|\s+and\s+|\s+or\s+)\s*", re.I)

AUDIT_PROMPT = """You audit a technical requirement extraction. You receive the job description and the extracted lists. Return one JSON object {"missed_terms": [str]} listing technical skills, programming languages, tools, frameworks, platforms, standards, methods, or engineering domains that the job description explicitly names but the extraction omitted. Each entry must be an atomic term copied exactly as spelled in the job description. Do not include soft skills, generic phrases, or anything not literally written in the job description. Return an empty list if nothing was missed."""


def _norm(value: str) -> str:
    return " ".join(str(value).strip().split())


def _in_text(term: str, text: str) -> bool:
    return bool(term) and re.search(r"(?<![\w+#])" + re.escape(term.casefold()) + r"(?![\w+#])", text.casefold()) is not None


def _grounded(term: str, text: str) -> bool:
    """A term is grounded if it, or all of its words, appear in the posting."""
    if _in_text(term, text):
        return True
    words = [w for w in re.findall(r"[\w+#.]+", term.casefold()) if len(w) > 2]
    return bool(words) and all(_in_text(w, text) for w in words)


def normalize_job(job_data: dict, source_text: str) -> dict:
    """Clean extraction output deterministically.

    Splits joined entries, removes duplicates across required/preferred, drops
    sentences from skill fields, and moves terms the posting never mentions into
    implicit_requirements so they stay visible but are not treated as stated.
    """
    result = dict(job_data)
    implicit = [_norm(v) for v in result.get("implicit_requirements", []) or [] if _norm(v)]
    seen_required: set[str] = set()
    for field in SKILL_FIELDS:
        cleaned: list[str] = []
        for raw in result.get(field, []) or []:
            raw = _norm(raw)
            if not raw:
                continue
            parts = [raw] if _in_text(raw, source_text) and len(raw.split()) <= 4 else SPLIT_PATTERN.split(raw)
            for part in parts:
                part = _norm(part).strip(".:()")
                if not part or len(part.split()) > 6:
                    continue
                key = part.casefold()
                if key in {c.casefold() for c in cleaned}:
                    continue
                if field == "preferred_skills" and key in seen_required:
                    continue
                if not _grounded(part, source_text):
                    if part.casefold() not in {i.casefold() for i in implicit}:
                        implicit.append(part)
                    continue
                cleaned.append(part)
                if field == "required_skills":
                    seen_required.add(key)
        result[field] = cleaned
    result["implicit_requirements"] = list(dict.fromkeys(implicit))
    return result


def _audit_missed_terms(job_data: dict, source_text: str) -> list[str]:
    known = {v.casefold() for f in (*SKILL_FIELDS, "implicit_requirements") for v in job_data.get(f, [])}
    try:
        reply = complete_json(
            AUDIT_PROMPT,
            {"job_description": source_text, "extracted": {f: job_data.get(f, []) for f in SKILL_FIELDS}},
            model=JD_MODEL,
        )
    except Exception:
        return []
    terms = reply.get("missed_terms", [])
    if not isinstance(terms, list):
        return []
    return [t for t in (_norm(x) for x in terms if isinstance(x, str)) if t and t.casefold() not in known and _in_text(t, source_text) and len(t.split()) <= 4]


def analyze_job(text: str) -> JobAnalysis:
    """Extract job requirements with AI; never silently substitute keyword heuristics."""
    cleaned_text = text.strip()
    if len(cleaned_text) < 30:
        raise ValueError("Please provide a job description with at least 30 characters.")
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "AI job extraction requires OPENAI_API_KEY. Add it to the project .env file and restart the app."
        )

    try:
        result = complete_json(
            EXTRACTION_PROMPT,
            {
                "job_description": cleaned_text,
                "output_schema": JobAnalysis.model_json_schema(),
            },
            model=JD_MODEL,
        )
        result = normalize_job(result, cleaned_text)
        # Terms the audit finds are literal text from the posting, so they are safe to add.
        for term in _audit_missed_terms(result, cleaned_text):
            result["technical_skills"] = [*result.get("technical_skills", []), term]
        result["analysis_method"] = "AI-assisted"
        result["analysis_warning"] = ""
        return JobAnalysis.model_validate(result)
    except Exception as exc:
        raise RuntimeError(
            f"AI job extraction failed ({type(exc).__name__}). No keyword-based fallback was used; please retry."
        ) from exc
