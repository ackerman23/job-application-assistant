import pytest

from app.models.schemas import CandidateProfile, JobAnalysis
from app.services import matching_engine


def _inputs():
    return JobAnalysis(role_title="Dev", company="Acme", required_skills=["Python"]), CandidateProfile()


def test_ai_failure_raises_instead_of_falling_back(monkeypatch):
    monkeypatch.delenv("ALLOW_LOCAL_MATCHING", raising=False)
    monkeypatch.setattr(matching_engine, "OPENAI_API_KEY", "key")
    monkeypatch.setattr(matching_engine, "_match_job_ai", lambda *a: (_ for _ in ()).throw(ValueError("bad")))
    with pytest.raises(RuntimeError, match="No local fallback"):
        matching_engine.match_job(*_inputs())


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("ALLOW_LOCAL_MATCHING", raising=False)
    monkeypatch.setattr(matching_engine, "OPENAI_API_KEY", "")
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        matching_engine.match_job(*_inputs())


def test_local_matching_is_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("ALLOW_LOCAL_MATCHING", "1")
    monkeypatch.setattr(matching_engine, "OPENAI_API_KEY", "")
    assert matching_engine.match_job(*_inputs()).matches is not None
