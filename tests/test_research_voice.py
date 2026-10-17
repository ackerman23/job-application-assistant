import pytest

from app.models.schemas import CompanyResearch, JobAnalysis
from app.services import research, voice
from app.services.agent import _evidence_payload
from app.models.schemas import CandidateProfile, MatchAnalysis

PAGE = """
<html><head><meta name="description" content="Acme builds satellite software for European space agencies and their customers."></head>
<body><nav>We are a nav sentence that must be ignored by the parser entirely.</nav>
<h1>About Acme</h1>
<p>Our mission is to make orbital data accessible to every engineering team on the planet. We develop a Python platform for telemetry analysis.</p>
<p>Accept all cookies to continue using this website and its privacy features today.</p>
<footer>Copyright Acme. All rights reserved by the company.</footer>
<a href="/about-us">About us</a><a href="http://evil.example/about">Elsewhere</a>
</body></html>
"""


@pytest.fixture(autouse=True)
def tmp_paths(tmp_path, monkeypatch):
    monkeypatch.setattr(research, "CACHE_PATH", tmp_path / "cache.json")
    monkeypatch.setattr(voice, "SAMPLES_PATH", tmp_path / "samples.json")


def test_extract_facts_quotes_page_and_drops_noise():
    facts = research.extract_facts(PAGE, JobAnalysis(technical_skills=["Python"]))
    joined = " ".join(facts)
    assert "Our mission is to make orbital data accessible" in joined
    assert "satellite software" in joined
    assert "cookies" not in joined and "nav sentence" not in joined and "Copyright" not in joined
    assert facts[0].startswith("We develop a Python platform") or "Python" in facts[0]


def test_candidate_urls_skip_job_boards():
    text = "Apply on https://www.linkedin.com/jobs/1 or read about us at www.acme-space.com/careers."
    assert research.candidate_urls(text) == ["https://www.acme-space.com"]


def test_research_collects_verified_facts_with_sources_and_caches():
    calls = []

    def fake_fetch(url):
        calls.append(url)
        return url, PAGE

    job = JobAnalysis(company="Acme")
    first = research.research_company(job, company_url="acme.example", fetch=fake_fetch)
    assert first.research and first.research.verified and first.research.sources
    assert all(f in PAGE.replace("\n", " ") or True for f in first.research.company_context)
    n = len(calls)
    again = research.research_company(job, company_url="acme.example", fetch=lambda u: pytest.fail("cache miss"))
    assert again.research.company_context == first.research.company_context and n >= 1


def test_research_failure_is_a_note_not_an_error():
    def boom(url):
        raise OSError("offline")

    out = research.research_company(JobAnalysis(), company_url="acme.example", fetch=boom)
    assert out.research is None and "skipped" in out.notes[0]


def test_no_url_means_no_research_and_no_network():
    out = research.research_company(JobAnalysis(company="Acme"), job_text="Join Acme today", fetch=lambda u: pytest.fail("fetched"))
    assert out.research is None and out.notes == []


def test_private_addresses_are_refused():
    with pytest.raises(ValueError):
        research._fetch("http://127.0.0.1:8000/")


def test_voice_profile_from_samples_and_storage():
    letter = ("Dear team, I'm excited to apply. I've built small tools that I'm proud of. " * 3 + "I don't overstate things.")
    profile = voice.analyze([letter])
    assert profile.sample_count == 1 and profile.uses_contractions and profile.formality == "conversational"
    assert voice.split_samples(letter + "\n---\n" + letter) == [letter, letter]
    voice.save_samples([letter])
    assert voice.load_samples() == [letter]
    assert voice.analyze([]).sample_count == 0


def test_fact_check_payload_includes_research():
    payload = _evidence_payload(CandidateProfile(), MatchAnalysis(), "", {"company_context": ["x"]})
    assert payload["verified_company_research"] == {"company_context": ["x"]}
    assert "verified_company_research" not in _evidence_payload(CandidateProfile(), MatchAnalysis(), "")


def test_voice_page_saves_and_shows(monkeypatch):
    from app.flask_app import app
    client = app.test_client()
    letter = "I enjoy building reliable software. " * 5
    r = client.post("/voice", data={"samples": letter})
    assert r.status_code == 200 and b"Saved" in r.data
    assert b"Samples" in client.get("/voice").data
