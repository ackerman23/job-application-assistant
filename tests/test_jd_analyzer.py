import pytest

from app.models.schemas import JobAnalysis
from app.services import jd_analyzer


def test_job_analyzer_uses_ai_response_and_marks_method(monkeypatch):
    observed = {}

    def fake_complete_json(prompt, payload):
        observed["prompt"] = prompt
        observed["job_description"] = payload["job_description"]
        return {
            "company": "Example Space",
            "position": "Python Engineer",
            "required_skills": ["Python"],
            "technical_skills": ["Python"],
            "tools_and_technologies": ["Docker"],
            "soft_skills": ["communication"],
        }

    monkeypatch.setattr(jd_analyzer, "OPENAI_API_KEY", "configured-test-key")
    monkeypatch.setattr(jd_analyzer, "complete_json", fake_complete_json)

    result = jd_analyzer.analyze_job("  We need a Python engineer with Docker experience.  ")

    assert result.analysis_method == "AI-assisted"
    assert result.company == "Example Space"
    assert result.technical_skills == ["Python"]
    assert result.tools_and_technologies == ["Docker"]
    assert observed["job_description"] == "We need a Python engineer with Docker experience."
    assert "Do not put communication" in observed["prompt"]


def test_job_analyzer_requires_api_key_instead_of_using_keyword_fallback(monkeypatch):
    monkeypatch.setattr(jd_analyzer, "OPENAI_API_KEY", "")

    with pytest.raises(RuntimeError, match="requires OPENAI_API_KEY"):
        jd_analyzer.analyze_job("We need a Python engineer with Docker experience.")


def test_job_analyzer_surfaces_ai_failure_without_keyword_fallback(monkeypatch):
    def fail_ai(prompt, payload):
        raise ConnectionError("provider unavailable")

    monkeypatch.setattr(jd_analyzer, "OPENAI_API_KEY", "configured-test-key")
    monkeypatch.setattr(jd_analyzer, "complete_json", fail_ai)

    with pytest.raises(RuntimeError, match="No keyword-based fallback was used"):
        jd_analyzer.analyze_job("We need a Python engineer with Docker experience.")


def test_job_analyzer_rejects_too_short_input_before_calling_ai(monkeypatch):
    def unexpected_ai_call(prompt, payload):
        pytest.fail("AI should not be called for an invalid short description")

    monkeypatch.setattr(jd_analyzer, "OPENAI_API_KEY", "configured-test-key")
    monkeypatch.setattr(jd_analyzer, "complete_json", unexpected_ai_call)

    with pytest.raises(ValueError, match="at least 30 characters"):
        jd_analyzer.analyze_job("Python developer")
