from fastapi import APIRouter
from app.models.schemas import CandidateProfile
from app.services.profile_manager import load_profile, save_profile

router = APIRouter(prefix="/profiles", tags=["profiles"])

@router.get("/master", response_model=CandidateProfile)
def get_profile():
    return load_profile()

@router.put("/master", response_model=CandidateProfile)
def put_profile(profile: CandidateProfile):
    save_profile(profile)
    return profile
