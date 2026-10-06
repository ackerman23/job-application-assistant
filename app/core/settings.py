"""Validated, private user preferences loaded from YAML."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.models.schemas import MatchType


class CVSettings(BaseModel):
    """Preferences that affect CV tailoring and layout."""

    default_selected_match_types: list[MatchType] = Field(
        default_factory=lambda: [MatchType.VERIFIED, MatchType.TRANSFERABLE, MatchType.FAMILIARITY]
    )
    include_explicitly_selected_missing_skills: bool = True
    max_experience_entries: int = Field(default=10, ge=1, le=10)
    max_project_entries: int = Field(default=10, ge=1, le=10)

    @field_validator("default_selected_match_types")
    @classmethod
    def require_match_type(cls, value: list[MatchType]) -> list[MatchType]:
        if not value:
            raise ValueError("must include at least one match type")
        return list(dict.fromkeys(value))


class CoverLetterSettings(BaseModel):
    """Preferences that guide, but do not replace, evidence rules."""

    tone: str = "professional"
    technical_detail: str = "high"
    target_word_count: int = Field(default=375, ge=200, le=600)
    use_hiring_manager_review: bool = True
    focus_skills: list[str] = Field(default_factory=list)
    custom_instructions: str = ""

    @field_validator("tone", "technical_detail")
    @classmethod
    def limit_short_preference(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or len(cleaned) > 80:
            raise ValueError("must be between 1 and 80 characters")
        return cleaned

    @field_validator("focus_skills")
    @classmethod
    def limit_focus_skills(cls, value: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(item.strip() for item in value if item.strip()))
        if len(cleaned) > 12 or any(len(item) > 80 for item in cleaned):
            raise ValueError("must contain at most 12 skills of up to 80 characters each")
        return cleaned

    @field_validator("custom_instructions")
    @classmethod
    def limit_custom_instructions(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) > 1_000:
            raise ValueError("must contain at most 1000 characters")
        return cleaned


class UserSettings(BaseModel):
    """All supported user-editable settings."""

    cv: CVSettings = Field(default_factory=CVSettings)
    cover_letter: CoverLetterSettings = Field(default_factory=CoverLetterSettings)


ROOT = Path(__file__).resolve().parents[2]
USER_SETTINGS_PATH = ROOT / "config" / "user-settings.yaml"


def _settings_error(message: str) -> RuntimeError:
    return RuntimeError(f"Invalid user settings in {USER_SETTINGS_PATH}: {message}")


@lru_cache(maxsize=1)
def get_user_settings() -> UserSettings:
    """Load private settings, falling back to safe defaults when absent."""
    if not USER_SETTINGS_PATH.exists():
        return UserSettings()
    try:
        raw = yaml.safe_load(USER_SETTINGS_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise _settings_error(str(exc)) from exc
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise _settings_error("the root value must be a mapping")
    try:
        return UserSettings.model_validate(raw)
    except ValidationError as exc:
        raise _settings_error(str(exc)) from exc
