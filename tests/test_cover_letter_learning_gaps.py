from app.models.schemas import CandidateProfile, JobAnalysis, MatchAnalysis, MatchType, RequirementMatch
from app.services import generation
from app.services.generation import _approved_context, validate_generated_text
from types import SimpleNamespace


def test_missing_requirement_can_be_used_as_an_explicit_learning_goal():
    match = MatchAnalysis(
        matches=[RequirementMatch(requirement="Kubernetes", match_type=MatchType.MISSING, importance="HIGH")],
        learning_recommendations=[
            {"skill": "Kubernetes", "recommended_learning": "Deploy a small service and study cluster operations."}
        ],
    )

    result = validate_generated_text(
        "I have not used Kubernetes yet, and I would like to build that capability through practical work.",
        CandidateProfile(),
        match,
    )

    assert result["passed"] is True
    assert result["warnings"] == []


def test_missing_requirement_is_still_rejected_when_claimed_as_experience():
    match = MatchAnalysis(matches=[RequirementMatch(requirement="Kubernetes", match_type=MatchType.MISSING)])

    result = validate_generated_text(
        "I have implemented Kubernetes deployments in production.", CandidateProfile(), match
    )

    assert result["passed"] is False
    assert result["unsupported_claims"] == ["Kubernetes"]
    assert result["issues"] == ["Unsupported requirement presented as experience: Kubernetes"]


def test_approved_context_exposes_missing_gaps_and_supported_wording():
    match = MatchAnalysis(
        matches=[
            RequirementMatch(requirement="Python", match_type=MatchType.VERIFIED, recommended_wording="Built Python services"),
            RequirementMatch(requirement="Kubernetes", match_type=MatchType.MISSING, importance="HIGH"),
        ]
    )

    context = _approved_context(CandidateProfile(), JobAnalysis(), match)

    assert context["supported_requirements"] == [
        {"requirement": "Python", "status": "VERIFIED", "selected_wording": "Built Python services"}
    ]
    assert context["learning_gaps"][0]["requirement"] == "Kubernetes"


def test_generation_does_not_require_profile_experience_or_projects(monkeypatch):
    draft = "I am interested in developing the adjacent skills this role requires."
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    choices=[SimpleNamespace(message=SimpleNamespace(content=draft))]
                )
            )
        )
    )
    monkeypatch.setattr(generation, "_client", lambda: fake_client)

    assert generation.generate_cover_letter(CandidateProfile(), JobAnalysis(), MatchAnalysis()) == draft