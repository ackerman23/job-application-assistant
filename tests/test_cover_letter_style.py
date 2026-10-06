from types import SimpleNamespace

from app.models.schemas import CandidateProfile, Experience, JobAnalysis, MatchAnalysis
from app.services import generation
from app.services.generation import validate_cover_letter_style


def test_cover_letter_style_accepts_concise_three_paragraph_draft():
    paragraph = "Evidence supports this technical fit. " * 20
    draft = "\n\n".join([paragraph.strip()] * 3)

    assert validate_cover_letter_style(draft) == []


def test_cover_letter_style_flags_length_and_generic_phrases():
    draft = "I am writing to express my interest. I am passionate about technology."

    issues = validate_cover_letter_style(draft)

    assert any("roughly 280–320 words" in issue for issue in issues)
    assert any("2–4 readable paragraphs" in issue for issue in issues)
    assert any("generic cover-letter phrases" in issue for issue in issues)


def test_cover_letter_style_flags_repetitive_openings_and_em_dash():
    draft = (
        "I built the feature. I tested the system. I delivered the release. "
        + "Evidence supports this technical fit. " * 60
    )

    issues = validate_cover_letter_style(draft)

    assert any("sentence openings" in issue for issue in issues)


def test_cover_letter_style_flags_em_dash():
    draft = ("The project improved reliability — a result supported by the test data. " * 30)

    issues = validate_cover_letter_style(draft)

    assert any("em-dash" in issue for issue in issues)


def test_style_issues_are_advisory_and_do_not_block_letter_generation(monkeypatch):
    short_draft = "A role-specific draft based on my documented technical experience."
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=short_draft))]
                )
            )
        )
    )
    monkeypatch.setattr(generation, "_client", lambda: fake_client)
    profile = CandidateProfile(experience=[Experience(company="Example", role="Engineer")])

    result = generation.generate_cover_letter(profile, JobAnalysis(), MatchAnalysis())

    assert result == short_draft
    assert any("roughly 280–320 words" in note for note in validate_cover_letter_style(result))
