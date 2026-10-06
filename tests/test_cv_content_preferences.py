from app.models.schemas import CandidateProfile, Experience, JobAnalysis, MatchAnalysis, Skill
from app.services.generation import generate_cv_tex


def test_generated_cv_keeps_requested_experience_order_and_removes_freelance():
    profile = CandidateProfile(
        experience=[
            Experience(company="Bosch Rexroth", role="AI Engineer Intern"),
            Experience(company="Space Informatics and Satellite Systems", role="Student Research Assistant"),
            Experience(company="Zhengzhou University", role="Research Assistant"),
            Experience(company="Outsourcia Group", role="Customer Service Agent"),
        ]
    )

    tex = generate_cv_tex(profile, JobAnalysis(), MatchAnalysis(), [])

    positions = [
        tex.index("Bosch Rexroth"),
        tex.index("Space Informatics and Satellite Systems"),
        tex.index("Zhengzhou University"),
        tex.index("Outsourcia Group"),
    ]
    assert positions == sorted(positions)
    assert "Freelance Developer" not in tex


def test_generated_cv_keeps_all_profile_skills_in_three_skill_lines():
    skill_names = ["Python", "C++", "Satellite Systems", "MBSE Concepts", "ROS1", "MCP", "Troubleshooting"]
    profile = CandidateProfile(skills=[Skill(name=name) for name in skill_names])

    tex = generate_cv_tex(profile, JobAnalysis(), MatchAnalysis(), [])
    skills_section = tex.split(r"\section{Skills}", 1)[1].split(r"\section{Languages}", 1)[0]

    assert skills_section.count(r"\item{") == 3
    for name in skill_names:
        assert name in skills_section
