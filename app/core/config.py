import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
DATA_DIR = ROOT / "data"
APPLICATIONS_DIR = DATA_DIR / "applications"
PROFILE_PATH = DATA_DIR / "candidate_profile.json"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'applications.db'}")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Stage-specific models are optional. Every stage falls back to OPENAI_MODEL so
# existing deployments continue to work with one configured model.
JD_MODEL = os.getenv("JD_MODEL", OPENAI_MODEL)
RESEARCH_MODEL = os.getenv("RESEARCH_MODEL", OPENAI_MODEL)
MATCHING_MODEL = os.getenv("MATCHING_MODEL", OPENAI_MODEL)
NARRATIVE_MODEL = os.getenv("NARRATIVE_MODEL", OPENAI_MODEL)
WRITING_MODEL = os.getenv("WRITING_MODEL", OPENAI_MODEL)
EDITOR_MODEL = os.getenv("EDITOR_MODEL", OPENAI_MODEL)
CRITIC_MODEL = os.getenv("CRITIC_MODEL", OPENAI_MODEL)
VALIDATION_MODEL = os.getenv("VALIDATION_MODEL", OPENAI_MODEL)
DATA_DIR.mkdir(exist_ok=True)
APPLICATIONS_DIR.mkdir(exist_ok=True)
