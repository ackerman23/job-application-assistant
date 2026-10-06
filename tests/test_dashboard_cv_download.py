from pathlib import Path

from app.models.schemas import CandidateProfile, Education, Experience, JobAnalysis, MatchAnalysis, MatchType, Project, RequirementMatch, Skill
from app.flask_app import app


def _sample_profile() -> CandidateProfile:
    return CandidateProfile(
        personal={"name": "Test Candidate", "languages": ["English"]},
        education=[Education(institution="Example University", degree="BSc", field="Computing")],
        experience=[Experience(company="Example Co", role="Developer", responsibilities=["Built Python services."])],
        projects=[Project(name="Example", description="A test project.")],
        skills=[Skill(name="Python", status="VERIFIED", evidence=["Built Python services."])],
    )


def _sample_job_and_match() -> tuple[JobAnalysis, MatchAnalysis]:
    job = JobAnalysis(
        company="Airbus",
        position="Software Engineer",
        required_skills=["Python", "Kubernetes"],
    )
    match = MatchAnalysis(
        matches=[
            RequirementMatch(
                requirement="Python",
                importance="HIGH",
                match_type=MatchType.VERIFIED,
                candidate_evidence=["Built Python services."],
                recommended_wording="Python",
            ),
            RequirementMatch(
                requirement="Kubernetes",
                importance="HIGH",
                match_type=MatchType.MISSING,
            ),
        ]
    )
    return job, match


def test_dashboard_renders_analysis_state_and_actionable_high_priority_gap(monkeypatch):
    profile = _sample_profile()
    job, match = _sample_job_and_match()
    monkeypatch.setattr("app.flask_app.load_profile", lambda: profile)
    monkeypatch.setattr("app.flask_app.save_profile", lambda value: None)
    monkeypatch.setattr("app.flask_app.analyze_profile_for_job", lambda profile, text: (job, match))

    response = app.test_client().post(
        "/dashboard",
        data={"profile_json": profile.model_dump_json(), "job_text": "A sufficiently long job description for this test."},
    )

    assert response.status_code == 200
    assert b'name="job_analysis_json"' in response.data
    assert b'name="match_analysis_json"' in response.data
    assert b'Include evidence-backed skill in CV' in response.data
    assert b'Save as a learning target' in response.data
    assert b'not a CV claim' in response.data


def test_dashboard_download_returns_compiled_pdf_and_uses_selected_evidence(tmp_path, monkeypatch):
    profile = _sample_profile()
    job, match = _sample_job_and_match()
    monkeypatch.setattr("app.flask_app.load_profile", lambda: profile)
    monkeypatch.setattr("app.flask_app.save_profile", lambda value: None)
    monkeypatch.setattr("app.flask_app.APPLICATIONS_DIR", tmp_path)

    response = app.test_client().post(
        "/dashboard",
        data={
            "action": "download_pdf",
            "profile_json": profile.model_dump_json(),
            "job_text": "A sufficiently long job description for this test.",
            "job_analysis_json": job.model_dump_json(),
            "match_analysis_json": match.model_dump_json(),
            "selected_requirements": ["Python"],
            "learning_requirements": ["Kubernetes"],
        },
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf", response.get_data(as_text=True).split('<div class="error">')[-1].split("</div>")[0]
    assert response.data.startswith(b"%PDF")
    assert "Airbus Resume.pdf" in response.headers["Content-Disposition"]
    generated_tex = next(Path(tmp_path).glob("cv-download-*/tailored_cv.tex")).read_text(encoding="utf-8")
    learning_plan = next(Path(tmp_path).glob("cv-download-*/learning_plan.md")).read_text(encoding="utf-8")
    assert "Python" in generated_tex
    assert "Kubernetes" not in generated_tex
    assert "Kubernetes" in learning_plan
    assert "not included as a CV claim" in learning_plan
