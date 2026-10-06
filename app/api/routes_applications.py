from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.database.database import Application, SessionLocal
from app.services.profile_manager import load_profile
from app.services.workflow import analyze_profile_for_job

router = APIRouter(prefix="/applications", tags=["applications"])
APPLICATION_STATUSES = {"DRAFT", "REVIEW", "APPLIED", "INTERVIEW", "REJECTED", "OFFER"}

class AnalyzeApplication(BaseModel):
    job_description: str = Field(min_length=30)

@router.post("/analyze")
def analyze_application(payload: AnalyzeApplication):
    profile = load_profile()
    if not (profile.skills or profile.experience or profile.projects):
        raise HTTPException(400, "Add candidate evidence to the master profile first.")
    try:
        job, match = analyze_profile_for_job(profile, payload.job_description)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    with SessionLocal() as session:
        row = Application(company=job.company, position=job.position, job_description=payload.job_description, match_summary=match.summary, status="REVIEW")
        session.add(row); session.commit(); session.refresh(row)
        application_id = row.id
    return {"id": application_id, "job": job, "match": match}

@router.get("")
def history():
    with SessionLocal() as session:
        return [{"id": x.id, "company": x.company, "position": x.position, "date": x.date, "match_summary": x.match_summary, "cv_path": x.cv_path, "cover_letter_path": x.cover_letter_path, "status": x.status} for x in session.query(Application).order_by(Application.date.desc()).all()]

class StatusUpdate(BaseModel):
    status: str

@router.patch("/{application_id}/status")
def update_status(application_id: int, payload: StatusUpdate):
    status = payload.status.upper()
    if status not in APPLICATION_STATUSES:
        raise HTTPException(422, "Status must be one of: " + ", ".join(sorted(APPLICATION_STATUSES)))
    with SessionLocal() as session:
        row = session.get(Application, application_id)
        if row is None: raise HTTPException(404, "Application not found")
        row.status = status
        session.commit()
        return {"id": row.id, "status": row.status}
