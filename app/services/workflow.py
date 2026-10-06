"""Workflow orchestration for the refactored app stack."""

from __future__ import annotations

from app.models.schemas import CandidateProfile, CompanyResearch, JobAnalysis, MatchAnalysis, MatchType
from app.core.settings import get_user_settings
from app.services.jd_analyzer import analyze_job
from app.services.generation import generate_change_log, generate_cover_letter, generate_cv_tex
from app.services.matching_engine import match_job


def analyze_job_description(job_description: str) -> JobAnalysis:
    """Analyze a job description using the shared job-analysis operation."""
    return analyze_job(job_description)


def analyze_profile_for_job(profile: CandidateProfile, job_description: str) -> tuple[JobAnalysis, MatchAnalysis]:
    """Run the evidence-first analysis pipeline for a single job description."""
    job = analyze_job_description(job_description)
    match = match_job(job, profile)
    return job, match


def match_profile_to_job(profile: CandidateProfile, job: JobAnalysis) -> MatchAnalysis:
    """Match a candidate profile to an already-analyzed job."""
    return match_job(job, profile)


def generate_cv_document(
    profile: CandidateProfile,
    job: JobAnalysis,
    match: MatchAnalysis,
    selected_requirements: list[str] | None = None,
) -> dict[str, str]:
    """Generate CV source and its change log with consistent selection defaults.

    An omitted selection includes supported/familiarity requirements by default;
    an explicitly empty selection stays empty.
    """
    settings = get_user_settings().cv
    selected = selected_requirements
    if selected is None:
        selected = [
            item.requirement
            for item in match.matches
            if item.match_type in settings.default_selected_match_types
        ]
    return {
        "cv_latex": generate_cv_tex(profile, job, match, selected),
        "change_log": generate_change_log(match),
    }


def generate_cover_letter_document(
    profile: CandidateProfile,
    job: JobAnalysis,
    match: MatchAnalysis,
    applicant_notes: str = "",
    company_research: CompanyResearch | None = None,
    writing_samples: list[str] | None = None,
) -> str:
    """Generate a cover letter through the shared application workflow."""
    return generate_cover_letter(profile, job, match, applicant_notes, company_research, writing_samples)


def build_document_bundle(
    profile: CandidateProfile,
    job: JobAnalysis,
    match: MatchAnalysis,
    selected_requirements: list[str] | None = None,
) -> dict:
    """Generate all derived artifacts for a candidate/job match."""
    cv_document = generate_cv_document(profile, job, match, selected_requirements)
    doc = {
        "job": job.model_dump(mode="json"),
        "match": match.model_dump(mode="json"),
        **cv_document,
    }
    try:
        doc["cover_letter"] = generate_cover_letter_document(profile, job, match)
    except (RuntimeError, ValueError):
        doc["cover_letter"] = ""
    return doc
