import pytest

from app.models.schemas import CandidateProfile, Experience, JobAnalysis, Skill
from app.services import jd_analyzer, matching_engine

JD = "We need a Python and C++ developer with Docker and PostgreSQL. Nice to have: Rust. Strong communication."


def test_normalize_splits_dedupes_and_grounds():
    data = {
        "required_skills": ["Python/C++", "Docker", "Python", "Kubernetes"],
        "preferred_skills": ["Rust", "Docker"],
        "technical_skills": ["PostgreSQL"],
        "implicit_requirements": [],
    }
    out = jd_analyzer.normalize_job(data, JD)
    assert out["required_skills"] == ["Python", "C++", "Docker"]
    assert out["preferred_skills"] == ["Rust"]
    assert "Kubernetes" in out["implicit_requirements"]


def test_audit_only_adds_terms_literally_in_posting(monkeypatch):
    monkeypatch.setattr(jd_analyzer, "complete_json", lambda *a, **k: {"missed_terms": ["PostgreSQL", "Terraform", "Rust"]})
    found = jd_analyzer._audit_missed_terms({"required_skills": ["Rust"], "technical_skills": []}, JD)
    assert found == ["PostgreSQL"]


def test_audit_failure_is_harmless(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(jd_analyzer, "complete_json", boom)
    assert jd_analyzer._audit_missed_terms({}, JD) == []


def _profile():
    return CandidateProfile(
        skills=[Skill(name="PostgreSQL", evidence=["Used PostgreSQL"])],
        experience=[Experience(company="Acme", role="Dev", technologies=["PostgreSQL"])],
    )


def _row(kind, ids, conf=0.9):
    return {"requirement": "SQL", "importance": "HIGH", "match_type": kind, "evidence_indices": ids,
            "recommended_wording": "SQL", "confidence": conf}


def _run(monkeypatch, replies):
    monkeypatch.setattr(matching_engine, "OPENAI_API_KEY", "key")
    queue = list(replies)

    def fake(prompt, payload, model=None):
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(matching_engine, "complete_json", fake)
    return matching_engine.match_job(JobAnalysis(required_skills=["SQL"]), _profile())


def test_review_pass_can_upgrade_missed_evidence(monkeypatch):
    result = _run(monkeypatch, [{"matches": [_row("MISSING", [])]}, {"matches": [_row("TRANSFERABLE", [0])]}])
    assert result.matches[0].match_type == MatchType.TRANSFERABLE


def test_review_cannot_claim_without_valid_evidence(monkeypatch):
    result = _run(monkeypatch, [{"matches": [_row("MISSING", [])]}, {"matches": [_row("VERIFIED", [999])]}])
    assert result.matches[0].match_type == MatchType.MISSING


def test_review_failure_keeps_first_pass(monkeypatch):
    result = _run(monkeypatch, [{"matches": [_row("VERIFIED", [0])]}, RuntimeError("down")])
    assert result.matches[0].match_type == MatchType.VERIFIED


def test_first_pass_failure_with_good_review_still_works(monkeypatch):
    result = _run(monkeypatch, [{"nope": 1}, {"matches": [_row("VERIFIED", [0])]}])
    assert result.matches[0].match_type == MatchType.VERIFIED


from app.models.schemas import MatchType  # noqa: E402
