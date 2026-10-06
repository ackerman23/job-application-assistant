from app.models.schemas import CandidateProfile, Experience, JobAnalysis, MatchAnalysis, MatchType, RequirementMatch, Skill
from app.services.generation import generate_cv_tex


def test_selected_requirement_additions_do_not_hide_other_profile_skills():
    profile = CandidateProfile(
        skills=[
            Skill(name="Data Processing", status="VERIFIED", evidence=[]),
            Skill(name="Other", status="VERIFIED", evidence=[]),
        ]
    )
    job = JobAnalysis(company="Example", position="Engineer", required_skills=["Data processing pipeline"])
    match = MatchAnalysis(
        matches=[
            RequirementMatch(
                requirement="Data processing pipeline",
                importance="HIGH",
                match_type=MatchType.VERIFIED,
                candidate_evidence=["Data processing"],
                recommended_wording="Data processing pipeline",
                confidence=1.0,
            )
        ]
    )

    tex = generate_cv_tex(profile, job, match, ["data processing pipeline"])

    assert "Data Processing" in tex
    assert "Other" in tex


def test_selected_technical_skill_prioritizes_matching_experience_without_rewriting_it():
    relevant_bullet = "Built Python data pipelines for satellite telemetry analysis."
    other_bullet = "Prepared weekly project status documentation."
    profile = CandidateProfile(
        skills=[Skill(name="Python", status="VERIFIED", evidence=[relevant_bullet])],
        experience=[
            Experience(
                company="Example Systems",
                role="Engineering Intern",
                responsibilities=[other_bullet, relevant_bullet],
                technologies=["Python"],
            )
        ],
    )
    job = JobAnalysis(required_skills=["Python"])
    match = MatchAnalysis(
        matches=[
            RequirementMatch(
                requirement="Python",
                match_type=MatchType.VERIFIED,
                candidate_evidence=[f"Engineering Intern at Example Systems: {relevant_bullet}"],
            )
        ]
    )

    tex = generate_cv_tex(profile, job, match, ["Python"])

    assert tex.index(relevant_bullet) < tex.index(other_bullet)
    assert r"Programming \& Data" in tex
    assert "Python" in tex


def test_generated_cv_preserves_source_resume_layout_and_section_order():
    profile = CandidateProfile()
    tex = generate_cv_tex(profile, JobAnalysis(), MatchAnalysis(), [])

    assert r"\documentclass[letterpaper,11pt]{article}" in tex
    assert r"\usepackage{fancyhdr}" in tex
    assert r"\pagestyle{fancy}" in tex
    section_positions = [
        tex.index(r"\section{Education}"),
        tex.index(r"\section{Experience}"),
        tex.index(r"\section{Projects}"),
        tex.index(r"\section{Skills}"),
        tex.index(r"\section{Languages}"),
    ]
    assert section_positions == sorted(section_positions)


def test_selected_unsupported_requirement_is_added_as_a_skill():
    profile = CandidateProfile(skills=[Skill(name="Python", evidence=["Built Python services."])])
    job = JobAnalysis(required_skills=["Kubernetes"])
    match = MatchAnalysis(
        matches=[
            RequirementMatch(
                requirement="Kubernetes",
                match_type=MatchType.MISSING,
                recommended_wording="Kubernetes",
            )
        ]
    )

    tex = generate_cv_tex(profile, job, match, ["Kubernetes"])

    assert "Kubernetes" in tex
    assert "Learning focus" not in tex
    assert "Selected job keywords" not in tex
