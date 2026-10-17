import pytest


@pytest.fixture(autouse=True)
def no_live_ai(monkeypatch):
    """Keep tests hermetic: a real key in .env must never trigger network calls."""
    import app.services.cv_agent as cv_agent
    import app.services.generation as generation
    import app.services.jd_analyzer as jd_analyzer
    import app.services.llm as llm
    import app.services.matching_engine as matching_engine

    for module in (cv_agent, generation, jd_analyzer, llm, matching_engine):
        monkeypatch.setattr(module, "OPENAI_API_KEY", "", raising=False)
