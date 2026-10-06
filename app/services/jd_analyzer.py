"""AI-only job description extraction."""

from app.core.config import OPENAI_API_KEY
from app.models.schemas import JobAnalysis
from app.services.llm import complete_json


EXTRACTION_PROMPT = """Carefully analyze only the supplied job description and return one JSON object matching the supplied JobAnalysis schema.

Extract the role, company, location, employment details, responsibilities, required skills, preferred skills, technical skills, soft skills, engineering domains, education and language requirements, tools and technologies, implicit technical requirements, and keywords. Keep required, preferred, and implicit categories distinct. Do not add anything that is not stated or clearly required by the job description. Do not assess the candidate.

Technical focus is essential: technical_skills, tools_and_technologies, domain_keywords, required_skills, preferred_skills, and implicit_requirements must contain concise named technical capabilities, engineering domains, programming languages, platforms, tools, standards, or methods only. Do not put communication, teamwork, leadership, interpersonal skills, stakeholder management, organization, time management, personality traits, or generic behavior requirements into those technical fields. If relevant, put generic interpersonal requirements only in soft_skills; the application may exclude those from CV selection.

Prefer specific named terms over sentences. Preserve whether a requirement is mandatory or preferred when the text provides that distinction. Include only requirements supported by the supplied text. Set analysis_method to AI-assisted and analysis_warning to an empty string."""


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
        )
        result["analysis_method"] = "AI-assisted"
        result["analysis_warning"] = ""
        return JobAnalysis.model_validate(result)
    except Exception as exc:
        raise RuntimeError(
            f"AI job extraction failed ({type(exc).__name__}). No keyword-based fallback was used; please retry."
        ) from exc
