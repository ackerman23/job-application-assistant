"""FastAPI MCP entrypoint for the refactored application."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.core.config import APPLICATIONS_DIR
from app.mcp.adapters import adapt_cover_letter_pdf_service, adapt_cover_letter_service, adapt_cv_pdf_service
from app.mcp.registry import list_tools as registry_list_tools
from app.models.schemas import CandidateProfile, CompanyResearch, JobAnalysis, MatchAnalysis
from app.services.generation import compile_pdf
from app.services.profile_manager import load_profile, save_profile
from app.services.workflow import (
    analyze_job_description,
    generate_cv_document,
    match_profile_to_job,
)

app = FastAPI(title="Job Application MCP Server", version="0.1.0")


class JobTextPayload(BaseModel):
    text: str = Field(min_length=30)


class SaveProfilePayload(BaseModel):
    profile: CandidateProfile


class MatchPayload(BaseModel):
    profile: CandidateProfile
    job: JobAnalysis


class CvPayload(BaseModel):
    profile: CandidateProfile
    job: JobAnalysis
    match: MatchAnalysis
    selected_requirements: list[str] | None = None
    applicant_notes: str = ""
    company_research: CompanyResearch | None = None
    writing_samples: list[str] = Field(default_factory=list)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "mcp"}


@app.get("/tools")
def list_tools() -> list[str]:
    return registry_list_tools()


@app.get("/tool/profile.get_profile")
def get_profile_tool() -> dict:
    return load_profile().model_dump(mode="json")


@app.post("/tool/profile.save_profile")
def save_profile_tool(payload: SaveProfilePayload) -> dict:
    save_profile(payload.profile)
    return payload.profile.model_dump(mode="json")


@app.post("/tool/jobs.analyze_job")
def analyze_job_tool(payload: JobTextPayload) -> dict:
    try:
        return analyze_job_description(payload.text).model_dump(mode="json")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/tool/matches.match_job")
def match_job_tool(payload: MatchPayload) -> dict:
    return match_profile_to_job(payload.profile, payload.job).model_dump(mode="json")


@app.post("/tool/cv.generate_cv_tex")
def generate_cv_tool(payload: CvPayload) -> dict:
    document = generate_cv_document(payload.profile, payload.job, payload.match, payload.selected_requirements)
    return {"latex": document["cv_latex"], "change_log": document["change_log"]}


@app.post("/tool/cv.generate_cv_pdf")
def generate_cv_pdf_tool(payload: CvPayload) -> dict:
    try:
        return adapt_cv_pdf_service(payload.profile, payload.job, payload.match, payload.selected_requirements)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tool/documents.generate_cover_letter")
def generate_cover_letter_tool(payload: CvPayload) -> dict:
    try:
        if payload.company_research is None and not payload.writing_samples:
            return adapt_cover_letter_service(payload.profile, payload.job, payload.match, payload.applicant_notes)
        return adapt_cover_letter_service(payload.profile, payload.job, payload.match, payload.applicant_notes, payload.company_research, payload.writing_samples)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tool/documents.generate_cover_letter_pdf")
def generate_cover_letter_pdf_tool(payload: CvPayload) -> dict:
    try:
        if payload.company_research is None and not payload.writing_samples:
            return adapt_cover_letter_pdf_service(payload.profile, payload.job, payload.match, payload.applicant_notes)
        return adapt_cover_letter_pdf_service(payload.profile, payload.job, payload.match, payload.applicant_notes, payload.company_research, payload.writing_samples)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/tool/documents.compile_pdf")
def compile_pdf_tool(payload: dict) -> dict:
    tex = payload.get("tex") or payload.get("latex") or ""
    if not tex:
        raise HTTPException(status_code=400, detail="No LaTeX content provided.")
    out_dir = APPLICATIONS_DIR / "mcp-export"
    out_dir.mkdir(parents=True, exist_ok=True)
    tex_path = out_dir / "mcp_export.tex"
    tex_path.write_text(tex, encoding="utf-8")
    pdf = compile_pdf(tex_path)
    return {"path": str(pdf), "filename": pdf.name}
