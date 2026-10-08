"""Document routes for the Flask app."""

from flask import Blueprint, jsonify, request
from app.core.settings import resolve_document_language
from app.models.schemas import CandidateProfile, JobAnalysis, MatchAnalysis
from app.services.application_services import CoverLetterService, ApplicationWorkflowService
from app.services.generation import generate_letter_tex
from app.services.workflow import generate_cover_letter_document, generate_cv_document

documents_bp = Blueprint("documents", __name__, url_prefix="/documents")


@documents_bp.post("/generate-cv")
def generate_cv():
    payload = request.get_json(silent=True) or {}
    profile = CandidateProfile.model_validate(payload.get("profile", {}))
    job = JobAnalysis.model_validate(payload.get("job", {}))
    match = MatchAnalysis.model_validate(payload.get("match", {}))
    selected = payload.get("selected_requirements")
    document = ApplicationWorkflowService(generate_cv=generate_cv_document).generate_cv_document(
        profile, job, match, selected
    )
    return jsonify({"latex": document["cv_latex"], "change_log": document["change_log"]})


@documents_bp.post("/generate-letter")
def generate_letter():
    payload = request.get_json(silent=True) or {}
    profile = CandidateProfile.model_validate(payload.get("profile", {}))
    job = JobAnalysis.model_validate(payload.get("job", {}))
    match = MatchAnalysis.model_validate(payload.get("match", {}))
    text, style_suggestions = CoverLetterService(generate=generate_cover_letter_document).generate(
        profile, job, match, payload.get("applicant_notes", "")
    )
    return jsonify({
        "text": text,
        "latex": (
            generate_letter_tex(text, profile, job.company, job.position)
            if resolve_document_language(job.job_language) == "English"
            else generate_letter_tex(
                text, profile, job.company, job.position, resolve_document_language(job.job_language)
            )
        ),
        "company": job.company,
        "position": job.position,
        "style_suggestions": style_suggestions,
    })
