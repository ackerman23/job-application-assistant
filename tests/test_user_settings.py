import pytest

from app.core import settings
from app.models.schemas import CandidateProfile, JobAnalysis, MatchAnalysis, MatchType, RequirementMatch
from app.services import workflow


@pytest.fixture(autouse=True)
def clear_settings_cache():
    settings.get_user_settings.cache_clear()
    yield
    settings.get_user_settings.cache_clear()


def load_settings_from(path, monkeypatch):
    monkeypatch.setattr(settings, "USER_SETTINGS_PATH", path)
    return settings.get_user_settings()


def test_user_settings_use_safe_defaults_when_private_file_is_absent(tmp_path, monkeypatch):
    value = load_settings_from(tmp_path / "missing.yaml", monkeypatch)

    assert value.cv.default_selected_match_types == [
        MatchType.VERIFIED,
        MatchType.TRANSFERABLE,
        MatchType.FAMILIARITY,
    ]
    assert value.cv.max_experience_entries == 10
    assert value.cover_letter.target_word_count == 375


def test_user_settings_load_valid_yaml_preferences(tmp_path, monkeypatch):
    path = tmp_path / "user-settings.yaml"
    path.write_text(
        "cv:\n  max_project_entries: 2\ncover_letter:\n  tone: concise\n  focus_skills: [Python, Systems Engineering]\n",
        encoding="utf-8",
    )

    value = load_settings_from(path, monkeypatch)

    assert value.cv.max_project_entries == 2
    assert value.cover_letter.tone == "concise"
    assert value.cover_letter.focus_skills == ["Python", "Systems Engineering"]


def test_invalid_user_settings_show_the_file_path(tmp_path, monkeypatch):
    path = tmp_path / "user-settings.yaml"
    path.write_text("cover_letter:\n  target_word_count: 99\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Invalid user settings"):
        load_settings_from(path, monkeypatch)


def test_cv_default_selection_uses_user_match_type_preferences(monkeypatch):
    configured = settings.UserSettings.model_validate(
        {"cv": {"default_selected_match_types": ["VERIFIED"]}}
    )
    monkeypatch.setattr(workflow, "get_user_settings", lambda: configured)
    captured = {}
    monkeypatch.setattr(workflow, "generate_cv_tex", lambda profile, job, match, selected: captured.setdefault("selected", selected) or "CV")

    match = MatchAnalysis(
        matches=[
            RequirementMatch(requirement="Python", match_type=MatchType.VERIFIED),
            RequirementMatch(requirement="Docker", match_type=MatchType.TRANSFERABLE),
        ]
    )
    workflow.generate_cv_document(CandidateProfile(), JobAnalysis(), match)

    assert captured["selected"] == ["Python"]
