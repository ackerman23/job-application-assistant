from app.flask_app import app
from app.mcp.registry import list_tools
from app.models.schemas import CandidateProfile, Experience, JobAnalysis, MatchAnalysis, MatchType, RequirementMatch, Skill
from app.services.matching_engine import _job_skill_requirements
from app.services.workflow import build_document_bundle, generate_cv_document


def test_flask_root_and_health_endpoint():
    client = app.test_client()
    response = client.get("/")
    assert response.status_code == 200
    assert b"Job Application Assistant" in response.data

    health = client.get("/health")
    assert health.status_code == 200
    assert health.get_json()["status"] == "ok"


def test_dashboard_page_renders():
    client = app.test_client()
    response = client.get("/dashboard")
    assert response.status_code == 200
    assert b"Job description" in response.data


def test_jobs_analysis_route(monkeypatch):
    def fake_ai_extraction(prompt, payload):
        assert "technical_skills" in payload["output_schema"]["properties"]
        return {"technical_skills": ["Python"], "required_skills": ["Python"]}

    monkeypatch.setattr("app.services.jd_analyzer.complete_json", fake_ai_extraction)
    client = app.test_client()
    response = client.post(
        "/jobs/analyze",
        json={
            "text": "We are looking for a Python engineer with SQL and testing experience in a distributed systems team."
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert "required_skills" in data
    assert "preferred_skills" in data


def test_requirement_review_excludes_general_soft_skills_but_keeps_technical_items():
    job = JobAnalysis(
        required_skills=["Python", "communication skills", "teamwork"],
        preferred_skills=["stakeholder management", "Docker"],
        technical_skills=["SQL", "leadership"],
        tools_and_technologies=["Git"],
    )

    requirements = _job_skill_requirements(job)

    assert requirements == ["Python", "Docker", "SQL", "Git"]


def test_workflow_bundle_builds_document_artifacts():
    profile = CandidateProfile(
        skills=[Skill(name="Python", evidence=["Built Python services."])] ,
        experience=[
            Experience(
                company="Example Labs",
                role="Software Engineer",
                technologies=["Python", "SQL"],
                responsibilities=["Built backend services."],
                evidence_level="VERIFIED",
            )
        ],
    )
    job = JobAnalysis(required_skills=["Python"], technical_skills=["Python"], domain_keywords=["software"])
    match = MatchAnalysis(
        matches=[
            RequirementMatch(
                requirement="Python",
                importance="HIGH",
                match_type=MatchType.VERIFIED,
                candidate_evidence=["Built Python services."],
                recommended_wording="Python",
                confidence=0.9,
            )
        ],
        score=90,
        summary="Strong Python evidence.",
    )

    bundle = build_document_bundle(profile, job, match, ["Python"])
    assert bundle["cv_latex"]
    assert "change_log" in bundle
    assert "cover_letter" in bundle


def test_cv_workflow_keeps_profile_skills_with_omitted_or_empty_job_selection():
    profile = CandidateProfile(skills=[Skill(name="Python", evidence=["Built Python services."])])
    job = JobAnalysis(required_skills=["Python"], technical_skills=["Python"])
    match = MatchAnalysis(
        matches=[
            RequirementMatch(
                requirement="Python",
                importance="HIGH",
                match_type=MatchType.VERIFIED,
                candidate_evidence=["Built Python services."],
                recommended_wording="Python",
                confidence=0.9,
            )
        ]
    )

    default_document = generate_cv_document(profile, job, match)
    empty_selection_document = generate_cv_document(profile, job, match, [])

    assert "Python" in default_document["cv_latex"]
    assert "Python" in empty_selection_document["cv_latex"]


def test_mcp_cv_adapter_uses_the_shared_document_workflow():
    from app.mcp.adapters import adapt_cv_service

    profile = CandidateProfile(skills=[Skill(name="Python", evidence=["Built Python services."])])
    job = JobAnalysis(required_skills=["Python"], technical_skills=["Python"])
    match = MatchAnalysis(
        matches=[
            RequirementMatch(
                requirement="Python",
                importance="HIGH",
                match_type=MatchType.VERIFIED,
                candidate_evidence=["Built Python services."],
                recommended_wording="Python",
                confidence=0.9,
            )
        ]
    )

    adapted = adapt_cv_service(profile, job, match)
    shared = generate_cv_document(profile, job, match)

    assert adapted["tex"] == shared["cv_latex"]
    assert adapted["change_log"] == shared["change_log"]


def test_registry_exposes_tools():
    tools = list_tools()
    assert "profile.get_profile" in tools
    assert "jobs.analyze_job" in tools
    assert "cv.generate_cv_tex" in tools
