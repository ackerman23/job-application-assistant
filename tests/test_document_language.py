import json
from types import SimpleNamespace

from app.core.settings import resolve_document_language
from app.models.schemas import CandidateProfile, Experience, JobAnalysis, MatchAnalysis, Skill
from app.services import generation
from app.services import jd_analyzer


def test_document_language_automatically_follows_detected_job_language(monkeypatch):
    monkeypatch.setattr(
        "app.core.settings.get_user_settings",
        lambda: SimpleNamespace(document_language="auto"),
    )

    assert resolve_document_language("French") == "French"
    assert resolve_document_language("English") == "English"


def test_document_language_can_be_overridden_by_user_setting(monkeypatch):
    monkeypatch.setattr(
        "app.core.settings.get_user_settings",
        lambda: SimpleNamespace(document_language="french"),
    )

    assert resolve_document_language("English") == "French"


def test_job_analysis_extracts_the_job_description_language(monkeypatch):
    monkeypatch.setattr(jd_analyzer, "OPENAI_API_KEY", "test-key")

    def fake_complete_json(prompt, payload):
        assert "job_language" in payload["output_schema"]["properties"]
        assert "predominantly written in French" in prompt
        return {"job_language": "French"}

    monkeypatch.setattr(jd_analyzer, "complete_json", fake_complete_json)

    job = jd_analyzer.analyze_job("Nous recherchons une personne pour rejoindre notre équipe technique.")

    assert job.job_language == "French"


def test_cover_letter_prompt_requires_french_for_a_french_job(monkeypatch):
    received = {}
    settings = SimpleNamespace(
        cover_letter=SimpleNamespace(
            tone="professional",
            technical_detail="high",
            target_word_count=375,
            focus_skills=[],
            custom_instructions="",
            use_hiring_manager_review=False,
        )
    )
    monkeypatch.setattr(generation, "get_user_settings", lambda: settings)
    monkeypatch.setattr(generation, "_approved_context", lambda *args: {"job_language": "French"})

    class FakeClient:
        class Chat:
            class Completions:
                @staticmethod
                def create(**kwargs):
                    received["system_prompt"] = kwargs["messages"][0]["content"]
                    return SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content="Lettre française."))]
                    )

            completions = Completions()

        chat = Chat()

    class FakeEngine:
        @staticmethod
        def quality_report(*args):
            return SimpleNamespace(requires_review=False)

    monkeypatch.setattr(generation, "_client", lambda: FakeClient())
    monkeypatch.setattr(generation, "CoverLetterIntelligenceEngine", FakeEngine)

    result = generation.generate_cover_letter(
        CandidateProfile(), JobAnalysis(job_language="French"), MatchAnalysis()
    )

    assert result == "Lettre française."
    assert "Write the complete cover letter in French" in received["system_prompt"]


def test_french_cv_translates_profile_prose_but_preserves_names_and_skills(monkeypatch):
    profile = CandidateProfile(
        personal={"name": "Alex Candidate", "email": "alex@example.com"},
        experience=[
            Experience(
                company="Orbit Labs",
                role="Software Engineer Intern",
                responsibilities=["Built Python data pipelines."],
            )
        ],
        skills=[Skill(name="Python")],
    )

    def fake_translate(items_json: str) -> str:
        items = json.loads(items_json)
        return json.dumps(
            [{"id": item["id"], "text": f"FR: {item['text']}"} for item in items],
            ensure_ascii=False,
        )

    monkeypatch.setattr(generation, "resolve_document_language", lambda job_language: "French")
    monkeypatch.setattr(generation, "_translate_cv_items", fake_translate)

    tex = generation.generate_cv_tex(profile, JobAnalysis(job_language="French"), MatchAnalysis(), [])

    assert r"\section{Formation}" in tex
    assert r"\section{Expérience}" in tex
    assert r"\section{Compétences}" in tex
    assert r"\csname textbf\endcsname{\Large Alex Candidate}" in tex
    assert "extbf{\\Large" not in tex
    assert "FR: Built Python data pipelines." in tex
    assert "Orbit Labs" in tex
    assert "Alex Candidate" in tex
    assert "Python" in tex
    assert "FR: Built Python data pipelines." not in profile.experience[0].responsibilities[0]


def test_french_cover_letter_tex_localizes_heading_and_omits_missing_company():
    tex = generation.generate_letter_tex(
        "Je souhaite contribuer à cette équipe.",
        CandidateProfile(),
        "",
        "Ingénieur logiciel",
        "French",
    )

    assert "Lettre de motivation" in tex
    assert "Cover Letter" not in tex
    assert "Company not specified" not in tex
    assert "Objet : Ingénieur logiciel" in tex
