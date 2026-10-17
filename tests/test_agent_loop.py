from app.models.schemas import CandidateProfile, JobAnalysis, MatchAnalysis, MatchType, RequirementMatch
from app.services import agent


def _inputs():
    job = JobAnalysis(role_title="Dev", company="Acme", required_skills=["Python", "Kubernetes"])
    match = MatchAnalysis(
        analysis_method="AI-assisted",
        matches=[
            RequirementMatch(requirement="Python", importance="HIGH", match_type=MatchType.VERIFIED, candidate_evidence=["Built APIs in Python"], recommended_wording="Python", confidence=0.9),
            RequirementMatch(requirement="Kubernetes", importance="HIGH", match_type=MatchType.MISSING, candidate_evidence=[], recommended_wording="", confidence=0.0),
        ],
        score=50, summary="", learning_recommendations=[],
    )
    return CandidateProfile(), job, match


def _stub_models(monkeypatch, fact_rows, score):
    def fake(prompt, payload, model=None):
        if prompt is agent.FACT_CHECK_PROMPT:
            return {"unsupported_claims": fact_rows(payload["letter"])}
        return {"score": score(payload["letter"]), "issues": [], "revision_instructions": []}
    monkeypatch.setattr(agent, "complete_json", fake)


def test_unsupported_claim_is_revised_away(monkeypatch):
    profile, job, match = _inputs()
    _stub_models(
        monkeypatch,
        lambda t: [{"claim": "ran clusters", "reason": "no evidence"}] if "clusters" in t else [],
        lambda t: 90,
    )
    calls = []

    def revise(text, instructions):
        calls.append(instructions)
        return "I built Python APIs."

    result = agent.refine_cover_letter(
        "I built Python APIs and ran clusters.", profile=profile, job=job, match=match,
        applicant_notes="", revise=revise,
    )
    assert result.text == "I built Python APIs."
    assert result.revisions == 1 and not result.warnings
    assert any("ran clusters" in i for i in calls[0])


def test_style_never_beats_facts_and_warnings_are_surfaced(monkeypatch):
    profile, job, match = _inputs()
    _stub_models(
        monkeypatch,
        lambda t: [{"claim": "ran clusters", "reason": "no evidence"}] if "clusters" in t else [],
        lambda t: 95 if "clusters" in t else 70,
    )
    result = agent.refine_cover_letter(
        "I ran clusters.", profile=profile, job=job, match=match, applicant_notes="",
        revise=lambda t, i: "A plain letter.", max_revisions=1,
    )
    assert result.text == "A plain letter."


def test_unfixed_claims_are_reported_after_budget(monkeypatch):
    profile, job, match = _inputs()
    _stub_models(monkeypatch, lambda t: [{"claim": "ran clusters", "reason": "x"}], lambda t: 90)
    result = agent.refine_cover_letter(
        "I ran clusters.", profile=profile, job=job, match=match, applicant_notes="",
        revise=lambda t, i: t + " again", max_revisions=2,
    )
    assert len(result.rounds) == 3
    assert any("ran clusters" in w for w in result.warnings)


def test_checker_failure_degrades_to_rules(monkeypatch):
    profile, job, match = _inputs()

    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(agent, "complete_json", boom)
    result = agent.refine_cover_letter(
        "I built Python APIs.", profile=profile, job=job, match=match, applicant_notes="",
        revise=lambda t, i: t,
    )
    assert result.text == "I built Python APIs."
    assert any("unavailable" in w for w in result.warnings)
