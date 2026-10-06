import json
from app.core.config import PROFILE_PATH
from app.models.schemas import CandidateProfile


def load_profile() -> CandidateProfile:
    if not PROFILE_PATH.exists():
        save_profile(CandidateProfile())
    return CandidateProfile.model_validate_json(PROFILE_PATH.read_text(encoding="utf-8"))


def save_profile(profile: CandidateProfile) -> None:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(json.dumps(profile.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
