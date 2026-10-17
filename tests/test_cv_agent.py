from app.models.schemas import (
    CandidateProfile, Experience, JobAnalysis, MatchAnalysis, MatchType, Project, RequirementMatch, Skill,
)
from app.services import cv_agent


def _profile():
    return CandidateProfile(
        skills=[Skill(name="Python", evidence=["Built APIs"])],
        experience=[Experience(
            company="Acme", role="Engineer", technologies=["Python", "Docker"],
            responsibilities=["Maintained internal tools.", "Built REST APIs in Python serving 20 clients."],
            achievements=["Cut deployment time by 30%."],
        )],
        projects=[Project(name="Rover", description="Robot", responsibilities=["Wrote ROS nodes."], technologies=["ROS"])],
    )


def _match():
    def row(req, kind, imp, ev=()):
        return RequirementMatch(requirement=req, importance=imp, match_type=kind, candidate_evidence=list(ev),
                                recommended_wording=req if kind != MatchType.MISSING else "", confidence=0.8)
    return MatchAnalysis(matches=[
        row("REST API development", MatchType.VERIFIED, "HIGH", ["Engineer at Acme: Built REST APIs in Python"]),
        row("Kubernetes", MatchType.MISSING, "HIGH"),
    ])


def _run(monkeypatch, plan, verdict, **kw):
    def fake(prompt, payload, model=None):
        if prompt is cv_agent.PLAN_PROMPT:
            return plan(payload) if callable(plan) else plan
        if isinstance(verdict, Exception):
            raise verdict
        return verdict
    monkeypatch.setattr(cv_agent, "OPENAI_API_KEY", "key")
    monkeypatch.setattr(cv_agent, "complete_json", fake)
    return cv_agent.tailor_profile(_profile(), JobAnalysis(position="Dev"), _match(), None, **kw)


PLAN = {
    "experience": [{"index": 0,
        "responsibilities": [{"source": "r1", "text": "Built REST API development services in Python serving 20 clients."},
                             {"source": "r0", "text": "Maintained internal tools."}],
        "achievements": [{"source": "a0", "text": "Cut deployment time by 30%."}]}],
    "projects": [],
}


def test_verified_rewrite_is_applied_and_reordered(monkeypatch):
    profile, report = _run(monkeypatch, PLAN, {"unfaithful": []})
    exp = profile.experience[0]
    assert exp.responsibilities[0].startswith("Built REST API development")
    assert exp.responsibilities[1] == "Maintained internal tools."
    assert report.rewrites_accepted == 1 and report.rewrites_rejected == 0


def test_unfaithful_rewrite_reverts_to_original(monkeypatch):
    profile, report = _run(monkeypatch, PLAN, {"unfaithful": ["e0.r1"]})
    assert profile.experience[0].responsibilities[0] == "Built REST APIs in Python serving 20 clients."
    assert report.rewrites_rejected == 1


def test_verifier_failure_fails_closed(monkeypatch):
    profile, report = _run(monkeypatch, PLAN, RuntimeError("down"))
    assert profile.experience[0].responsibilities[0] == "Built REST APIs in Python serving 20 clients."
    assert any("Faithfulness check unavailable" in n for n in report.notes)


def test_invented_numbers_and_missing_skills_are_blocked(monkeypatch):
    plan = {"experience": [{"index": 0, "responsibilities": [
        {"source": "r0", "text": "Maintained internal tools for 500 users."},
        {"source": "r1", "text": "Built REST APIs in Python on Kubernetes."}], "achievements": []}], "projects": []}
    profile, report = _run(monkeypatch, plan, {"unfaithful": []})
    assert report.rewrites_accepted == 0
    assert profile.experience[0].responsibilities == ["Maintained internal tools.", "Built REST APIs in Python serving 20 clients."]


def test_no_bullet_is_lost_when_plan_omits_some(monkeypatch):
    plan = {"experience": [{"index": 0, "responsibilities": [{"source": "r1", "text": "Built REST APIs in Python serving 20 clients."}], "achievements": []}], "projects": []}
    profile, _ = _run(monkeypatch, plan, {"unfaithful": []})
    assert set(profile.experience[0].responsibilities) == {"Maintained internal tools.", "Built REST APIs in Python serving 20 clients."}
    assert profile.experience[0].achievements == ["Cut deployment time by 30%."]


def test_unknown_or_duplicate_sources_are_ignored(monkeypatch):
    plan = {"experience": [{"index": 0, "responsibilities": [
        {"source": "r9", "text": "Invented bullet."}, {"source": "r0", "text": "Maintained internal tools."},
        {"source": "r0", "text": "Maintained internal tools."}], "achievements": []}], "projects": []}
    profile, _ = _run(monkeypatch, plan, {"unfaithful": []})
    assert "Invented bullet." not in profile.experience[0].responsibilities
    assert len(profile.experience[0].responsibilities) == 2


def test_bullet_cap_applies(monkeypatch):
    profile, _ = _run(monkeypatch, PLAN, {"unfaithful": []}, max_bullets=1)
    assert len(profile.experience[0].responsibilities) == 1


def test_uncovered_requirement_triggers_one_replan(monkeypatch):
    calls = []

    def plan(payload):
        calls.append(payload["coverage_hints"])
        return PLAN if calls[1:] else {"experience": [], "projects": []}

    plan_text_without_term = {"experience": [{"index": 0, "responsibilities": [
        {"source": "r0", "text": "Maintained internal tools."}], "achievements": []}], "projects": []}
    calls.clear()
    _run(monkeypatch, lambda p: (calls.append(p["coverage_hints"]) or plan_text_without_term), {"unfaithful": []})
    assert len(calls) == 2 and calls[0] == [] and calls[1]


def test_planner_failure_keeps_profile(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(cv_agent, "OPENAI_API_KEY", "key")
    monkeypatch.setattr(cv_agent, "complete_json", boom)
    original = _profile()
    profile, report = cv_agent.tailor_profile(original, JobAnalysis(), _match(), None)
    assert profile is original and report.notes


def test_selected_missing_skill_stays_addable_to_cv_skills(monkeypatch):
    from app.services.generation import generate_cv_tex
    tex = generate_cv_tex(_profile(), JobAnalysis(position="Dev"), _match(), ["Kubernetes"])
    assert "Kubernetes" in tex
    assert hasattr(tex, "report")
