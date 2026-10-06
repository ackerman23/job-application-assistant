from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.workflow import analyze_job_description

router = APIRouter(prefix="/jobs", tags=["jobs"])

class JobText(BaseModel):
    text: str = Field(min_length=30)

@router.post("/analyze")
def analyze(payload: JobText):
    try:
        return analyze_job_description(payload.text)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
