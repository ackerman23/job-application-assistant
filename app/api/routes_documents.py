import shutil
import tempfile
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException
from app.core.settings import resolve_document_language
from fastapi.responses import FileResponse
from pydantic import Field
from app.models.schemas import CandidateProfile, CompanyResearch, JobAnalysis, MatchAnalysis
from app.core.config import APPLICATIONS_DIR
from app.services.generation import company_document_stem, validate_generated_text, compile_pdf, generate_letter_tex, validate_cover_letter_style
from app.services.workflow import generate_cover_letter_document, generate_cv_document

router = APIRouter(prefix="/documents", tags=["documents"])

from pydantic import BaseModel
class DocumentInput(BaseModel):
    profile: CandidateProfile
    job: JobAnalysis
    match: MatchAnalysis
    selected_requirements: list[str] | None = None
    applicant_notes: str = ""
    company_research: CompanyResearch | None = None
    writing_samples: list[str] = Field(default_factory=list)


def _generate_letter(data: DocumentInput) -> str:
    if data.company_research is None and not data.writing_samples:
        return generate_cover_letter_document(data.profile, data.job, data.match, data.applicant_notes)
    return generate_cover_letter_document(data.profile, data.job, data.match, data.applicant_notes, data.company_research, data.writing_samples)

@router.post("/cv")
def cv(data: DocumentInput, background_tasks: BackgroundTasks):
    work_dir = Path(tempfile.mkdtemp(prefix="cv-download-", dir=APPLICATIONS_DIR))
    tex_path = work_dir / "tailored_cv.tex"
    try:
        document = generate_cv_document(data.profile, data.job, data.match, data.selected_requirements)
        tex_path.write_text(document["cv_latex"], encoding="utf-8")
        pdf_path = compile_pdf(tex_path)
    except Exception as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(400, f"Could not compile the CV PDF: {exc}") from exc
    background_tasks.add_task(shutil.rmtree, work_dir, ignore_errors=True)
    filename = f"{company_document_stem(data.job.company, 'Resume')}.pdf"
    return FileResponse(pdf_path, media_type="application/pdf", filename=filename)

@router.post("/cv/latex")
def cv_latex(data: DocumentInput):
    document = generate_cv_document(data.profile, data.job, data.match, data.selected_requirements)
    return {"latex": document["cv_latex"], "change_log": document["change_log"]}

@router.post("/cover-letter")
def cover_letter(data: DocumentInput):
    try:
        text = _generate_letter(data)
        return {"text": text, "style_suggestions": validate_cover_letter_style(text)}
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/cover-letter/latex")
def cover_letter_latex(data: DocumentInput):
    try:
        text = _generate_letter(data)
        language = resolve_document_language(data.job.job_language)
        latex = (
            generate_letter_tex(text, data.profile, data.job.company, data.job.position)
            if language == "English"
            else generate_letter_tex(text, data.profile, data.job.company, data.job.position, language)
        )
        return {
            "text": text,
            "latex": latex,
            "company": data.job.company,
            "position": data.job.position,
            "style_suggestions": validate_cover_letter_style(text),
        }
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/cover-letter/pdf")
def cover_letter_pdf(data: DocumentInput, background_tasks: BackgroundTasks):
    work_dir = Path(tempfile.mkdtemp(prefix="cover-letter-download-", dir=APPLICATIONS_DIR))
    tex_path = work_dir / "cover_letter.tex"
    try:
        text = _generate_letter(data)
        language = resolve_document_language(data.job.job_language)
        rendered_letter = (
            generate_letter_tex(text, data.profile, data.job.company, data.job.position)
            if language == "English"
            else generate_letter_tex(text, data.profile, data.job.company, data.job.position, language)
        )
        tex_path.write_text(rendered_letter, encoding="utf-8")
        pdf_path = compile_pdf(tex_path)
    except (RuntimeError, ValueError) as exc:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise HTTPException(400, f"Could not generate the cover letter PDF: {exc}") from exc
    background_tasks.add_task(shutil.rmtree, work_dir, ignore_errors=True)
    filename = f"{company_document_stem(data.job.company, 'Cover Letter')}.pdf"
    return FileResponse(pdf_path, media_type="application/pdf", filename=filename)

@router.post("/quality-check")
def quality_check(data: DocumentInput, text: str):
    return validate_generated_text(text, data.profile, data.match)
