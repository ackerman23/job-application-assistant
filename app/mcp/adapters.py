"""Adapters to bridge the current service layer to MCP tools."""

import tempfile
from pathlib import Path

from app.core.config import APPLICATIONS_DIR
from app.services.generation import company_document_stem, compile_pdf, generate_letter_tex, validate_cover_letter_style
from app.services.workflow import analyze_profile_for_job, generate_cover_letter_document, generate_cv_document


def adapt_profile_service(profile):
    return {"profile": profile.model_dump(mode="json")}


def adapt_job_service(job_text: str, profile):
    job, match = analyze_profile_for_job(profile, job_text)
    return {"job": job.model_dump(mode="json"), "match": match.model_dump(mode="json")}


def adapt_cv_service(profile, job, match, selected_requirements=None):
    document = generate_cv_document(profile, job, match, selected_requirements)
    return {
        "tex": document["cv_latex"],
        "change_log": document["change_log"],
    }


def adapt_cv_pdf_service(profile, job, match, selected_requirements=None):
    document = generate_cv_document(profile, job, match, selected_requirements)
    output_dir = Path(tempfile.mkdtemp(prefix="cv-tool-", dir=APPLICATIONS_DIR))
    stem = company_document_stem(job.company, "Resume")
    tex_path = output_dir / f"{stem}.tex"
    tex_path.write_text(document["cv_latex"], encoding="utf-8")
    pdf_path = compile_pdf(tex_path)
    return {"pdf_path": str(pdf_path), "filename": pdf_path.name, "change_log": document["change_log"]}


def adapt_cover_letter_service(profile, job, match, applicant_notes="", company_research=None, writing_samples=None):
    if company_research is None and not writing_samples:
        letter = generate_cover_letter_document(profile, job, match, applicant_notes)
    else:
        letter = generate_cover_letter_document(profile, job, match, applicant_notes, company_research, writing_samples)
    latex = generate_letter_tex(letter, profile, job.company, job.position)
    return {
        "text": letter,
        "latex": latex,
        "company": job.company,
        "position": job.position,
        "style_suggestions": validate_cover_letter_style(letter),
    }


def adapt_cover_letter_pdf_service(profile, job, match, applicant_notes="", company_research=None, writing_samples=None):
    document = adapt_cover_letter_service(profile, job, match, applicant_notes, company_research, writing_samples)
    output_dir = Path(tempfile.mkdtemp(prefix="cover-letter-tool-", dir=APPLICATIONS_DIR))
    stem = company_document_stem(job.company, "Cover Letter")
    tex_path = output_dir / f"{stem}.tex"
    tex_path.write_text(document["latex"], encoding="utf-8")
    pdf_path = compile_pdf(tex_path)
    return {**document, "pdf_path": str(pdf_path), "filename": pdf_path.name}
