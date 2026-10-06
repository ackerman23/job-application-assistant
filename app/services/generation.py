import json
import re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.core.config import EDITOR_MODEL, OPENAI_API_KEY, OPENAI_MODEL, ROOT, WRITING_MODEL
from app.core.settings import get_user_settings
from app.models.schemas import CandidateProfile, CompanyResearch, JobAnalysis, MatchAnalysis, MatchType
from app.services.cover_letter_engine import CoverLetterIntelligenceEngine

PROMPTS = ROOT / "app" / "prompts"

COVER_LETTER_CLICHES = (
    "i am writing to express my interest",
    "i am excited to apply",
    "passionate about",
    "excited to contribute",
    "eager to learn",
    "fast-moving environment",
    "collaborative team",
    "innovative company",
    "i look forward to hearing from you at your earliest convenience",
    "i look forward to hearing from you",
)

ALIASES = {
    "postgresql": "database",
    "sql": "database",
    "gds": "satellite",
    "telemetry": "satellite",
    "ground": "satellite",
    "validation": "testing",
    "sysml": "systems",
    "mbse": "systems",
}


def _normalize_requirement(value: str) -> str:
    return " ".join(str(value).strip().split()).casefold()


def _requirement_tokens(value: str) -> set[str]:
    tokens = set(re.findall(r"[a-z0-9+#]+", _normalize_requirement(value)))
    expanded = set()
    for token in tokens:
        expanded.add(token)
        expanded.add(ALIASES.get(token, token))
    return expanded


def _is_related_requirement(skill_name: str, requirement: str) -> bool:
    skill_tokens = _requirement_tokens(skill_name)
    requirement_tokens = _requirement_tokens(requirement)
    if not skill_tokens or not requirement_tokens:
        return _normalize_requirement(skill_name) == _normalize_requirement(requirement)
    normalized_skill = _normalize_requirement(skill_name)
    normalized_requirement = _normalize_requirement(requirement)
    return (
        bool(skill_tokens & requirement_tokens)
        or skill_tokens <= requirement_tokens
        or requirement_tokens <= skill_tokens
        or normalized_skill in normalized_requirement
        or normalized_requirement in normalized_skill
    )


def _client():
    if not OPENAI_API_KEY:
        raise RuntimeError("Set OPENAI_API_KEY in .env to generate tailored prose. Local analysis and template export work without it.")
    from openai import OpenAI
    return OpenAI(api_key=OPENAI_API_KEY)


def _approved_context(
    profile: CandidateProfile,
    job: JobAnalysis,
    match: MatchAnalysis,
    applicant_notes: str = "",
    company_research: CompanyResearch | None = None,
    writing_samples: list[str] | None = None,
) -> dict:
    engine = CoverLetterIntelligenceEngine()
    understanding = engine.understand_job(job)
    hiring_need = engine.identify_hiring_need(job, understanding)
    research = engine.accept_verified_research(company_research) if company_research else engine.research_company(job).as_model()
    evidence = engine.retrieve_evidence(profile)
    intersections = engine.find_intersections(match)
    narrative = engine.build_narrative(profile, job, intersections, applicant_notes)
    strategy = engine.build_strategy(profile, job, hiring_need, intersections, research, applicant_notes)
    voice = engine.analyze_voice(writing_samples if writing_samples is not None else profile.writing_samples)
    learning_gaps = [
        {
            "requirement": item.requirement,
            "importance": item.importance,
            "current_status": item.match_type.value,
            "learning_recommendation": next(
                (
                    recommendation.get("recommended_learning", "")
                    for recommendation in match.learning_recommendations
                    if recommendation.get("skill", "").casefold() == item.requirement.casefold()
                ),
                "Build familiarity through focused study and a small practical exercise.",
            ),
        }
        for item in match.matches
        if item.match_type == MatchType.MISSING
    ]
    supported_requirements = [
        {
            "requirement": item.requirement,
            "status": item.match_type.value,
            "selected_wording": item.recommended_wording,
        }
        for item in match.matches
        if item.match_type in (MatchType.VERIFIED, MatchType.TRANSFERABLE, MatchType.FAMILIARITY)
    ]
    settings = get_user_settings().cover_letter
    return {
        "candidate": profile.model_dump(mode="json"),
        "job": job.model_dump(mode="json"),
        "match": match.model_dump(mode="json"),
        "applicant_notes": applicant_notes.strip(),
        "job_understanding": understanding.model_dump(mode="json"),
        "hiring_need": hiring_need.model_dump(mode="json"),
        "company_research": research.model_dump(mode="json"),
        "candidate_evidence_records": [item.model_dump(mode="json") for item in evidence],
        "candidate_role_intersections": [item.model_dump(mode="json") for item in intersections],
        "application_narrative": narrative.model_dump(mode="json"),
        "application_strategy": strategy.model_dump(mode="json"),
        "voice_profile": voice.model_dump(mode="json"),
        "learning_gaps": learning_gaps,
        "supported_requirements": supported_requirements,
        "user_preferences": {
            "tone": settings.tone,
            "technical_detail": settings.technical_detail,
            "target_word_count": settings.target_word_count,
            "focus_skills": settings.focus_skills,
            "custom_instructions": settings.custom_instructions,
        },
        "rules": "Use only profile, job description, applicant-note facts, and verified research facts. Never invent details, tools, outcomes, metrics, motivations, dates, company knowledge, teams, customers, or proprietary systems. Familiarity may only be described as familiarity. Do not represent transferable experience as direct experience. Missing requirements may be named, but only as a clearly acknowledged learning gap, learning goal, or motivation to develop; never present them as current experience. Prefer one or two relevant gaps over listing every gap. Preserve supported and selected skill/tool wording when it is useful to the letter.",
    }


def generate_cover_letter(
    profile: CandidateProfile,
    job: JobAnalysis,
    match: MatchAnalysis,
    applicant_notes: str = "",
    company_research: CompanyResearch | None = None,
    writing_samples: list[str] | None = None,
) -> str:
    context = _approved_context(profile, job, match, applicant_notes, company_research, writing_samples)
    settings = get_user_settings().cover_letter
    system_prompt = (PROMPTS / "cover_letter.txt").read_text(encoding="utf-8")
    system_prompt += (
        "\n\nUSER PREFERENCES\n"
        "Apply these preferences when they do not conflict with the evidence, honesty, and factuality rules above. "
        f"Tone: {settings.tone}. Technical detail: {settings.technical_detail}. "
        f"Target length: approximately {settings.target_word_count} words. "
        f"Prioritize these supported themes when relevant: {', '.join(settings.focus_skills) or 'none specified'}. "
        f"Additional user instructions: {settings.custom_instructions or 'none'}."
    )
    from openai import APIConnectionError, AuthenticationError, RateLimitError
    client = _client()
    try:
        response = client.chat.completions.create(model=WRITING_MODEL, temperature=0.65, messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": json.dumps(context, ensure_ascii=False)}])
    except AuthenticationError as exc:
        raise RuntimeError("OpenAI rejected the API key. Check that it is active and belongs to the intended OpenAI project, then restart the app.") from exc
    except RateLimitError as exc:
        raise RuntimeError("OpenAI rejected the request because of rate or usage limits. Check the project's API billing and limits.") from exc
    except APIConnectionError as exc:
        raise RuntimeError("Could not connect to the OpenAI API. Check your internet connection and try again.") from exc
    result = response.choices[0].message.content or ""
    quality = CoverLetterIntelligenceEngine().quality_report(result, job, match)
    if settings.use_hiring_manager_review and quality.requires_review:
        editor_context = {
            **context,
            "draft_to_edit": result,
            "quality_report": quality.model_dump(mode="json"),
            "editor_instruction": "Rewrite only where necessary. Keep supported concrete details, remove generic language, and return only the revised final letter.",
        }
        try:
            edited = client.chat.completions.create(
                model=EDITOR_MODEL,
                temperature=0.65,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(editor_context, ensure_ascii=False)},
                ],
            )
            result = edited.choices[0].message.content or result
        except (AuthenticationError, RateLimitError, APIConnectionError):
            # A first draft is still useful when the optional editor pass fails.
            pass
    # Factuality checks remain available to the quality-check endpoint and UI,
    # but they are advisory here. The prompt tells the writer how to frame gaps
    # honestly, so a draft is not discarded merely because it discusses a gap.
    return result


def validate_cover_letter_style(text: str) -> list[str]:
    """Return deterministic style/format issues for a cover-letter draft."""
    normalized = " ".join(text.casefold().split())
    issues = []
    word_count = len(re.findall(r"\b[\w+#]+(?:[’'-][\w+#]+)*\b", text, flags=re.UNICODE))
    if not 300 <= word_count <= 400:
        issues.append(f"Consider a cover letter of roughly 280–320 words as the legacy baseline; the intelligence engine targets 350–400 words, about 375 (current count: {word_count}). This is only a suggestion.")

    paragraphs = [part for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]
    if not 2 <= len(paragraphs) <= 5:
        issues.append(f"Consider 2–4 readable paragraphs (current count: {len(paragraphs)}). This is only a suggestion.")

    used_cliches = [phrase for phrase in COVER_LETTER_CLICHES if phrase in normalized]
    if used_cliches:
        issues.append("Replace generic cover-letter phrases: " + ", ".join(used_cliches) + ".")
    if "—" in text:
        issues.append("Remove em-dash styling; use straightforward punctuation.")

    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text.strip()) if sentence.strip()]
    starts_with_i = [bool(re.match(r"^[\"'“‘(]*I\b", sentence)) for sentence in sentences]
    if any(starts_with_i[index:index + 3] == [True, True, True] for index in range(max(0, len(starts_with_i) - 2))):
        issues.append("Vary sentence openings; avoid three consecutive sentences beginning with ‘I’.")
    return issues


def generate_cv_tex(profile: CandidateProfile, job: JobAnalysis, match: MatchAnalysis, selected_requirements: list[str] | None = None) -> str:
    settings = get_user_settings().cv
    env = Environment(loader=FileSystemLoader(ROOT / "templates" / "cv"), autoescape=select_autoescape())
    env.filters["latex_escape"] = lambda value: str(value).replace("\\", r"\textbackslash{}").replace("&", r"\&").replace("%", r"\%").replace("$", r"\$").replace("#", r"\#").replace("_", r"\_").replace("{", r"\{").replace("}", r"\}")
    selection_gate = selected_requirements is not None
    requested = {_normalize_requirement(value) for value in (selected_requirements or [])}
    selected_matches = [
        item for item in match.matches
        if item.match_type in (MatchType.VERIFIED, MatchType.TRANSFERABLE, MatchType.FAMILIARITY, MatchType.MISSING)
        and (settings.include_explicitly_selected_missing_skills or item.match_type != MatchType.MISSING)
        and (not selection_gate or _normalize_requirement(item.requirement) in requested)
    ]
    targets = [m.requirement for m in selected_matches if len(m.requirement.split()) <= 7]
    target_tokens = set(re.findall(r"[a-z0-9+#]+", " ".join(targets).lower()))

    def relevance_score(value: str) -> int:
        value_tokens = set(re.findall(r"[a-z0-9+#]+", value.casefold()))
        return len(target_tokens & value_tokens)

    def rank(item):
        source = item.model_dump_json()
        score = relevance_score(source)
        name = str(getattr(item, "name", getattr(item, "role", ""))).casefold()
        for result in selected_matches:
            if any(name and name in evidence.casefold() for evidence in result.candidate_evidence):
                score += 10
        return score
    categories = [
        ("Programming & Data", ("python", "c++", "java", "javascript", "kotlin", "sql", "data", "database", "scripting", "pandas", "scientific computing", "optimization")),
        ("Space & Systems Engineering", ("space", "satellite", "spacecraft", "ground segment", "telemetry", "telecommand", "avionics", "attitude", "gds", "embedded", "systems", "sysml", "mbse", "requirements", "sedb", "srdb")),
        ("Software, AI & Engineering", ("ros", "postgresql", "rest api", "fastapi", "docker", "git", "linux", "matlab", "simulink", "tcp", "udp", "integration", "testing", "validation", "ai", "llm", "mcp", "neural", "vision", "backend", "object-oriented", "documentation", "technical analysis", "troubleshooting", "engineering")),
    ]
    # The user's master-profile skills stay visible even when a job-specific
    # selection is empty; selections only control job-derived additions.
    cv_skills = list(profile.skills)
    skill_groups = [
        {"name": name, "verified": [], "familiarity": [], "related": [], "learning": [], "unverified": [], "relevance": 0}
        for name, _ in categories
    ]
    for skill in cv_skills:
        category = next(
            (name for name, hints in categories if any(hint in skill.name.casefold() for hint in hints)),
            categories[-1][0],
        )
        group = next(item for item in skill_groups if item["name"] == category)
        group["verified" if skill.status.value == "VERIFIED" else "familiarity"].append(skill.name)
        group["relevance"] += rank(skill)
    group_hints = {name: hints for name, hints in categories}
    for result in selected_matches:
        normalized_requirement = _normalize_requirement(result.requirement)
        wording = result.requirement if result.match_type in (MatchType.VERIFIED, MatchType.MISSING) else (f"Familiarity with {result.requirement}" if result.match_type == MatchType.FAMILIARITY else result.recommended_wording)
        if not wording:
            continue
        haystack = (result.requirement + " " + wording).casefold()
        category = next((name for name, hints in group_hints.items() if any(hint in haystack for hint in hints)), categories[-1][0])
        group = next(item for item in skill_groups if item["name"] == category)
        existing = {_normalize_requirement(item) for item in group["verified"] + group["familiarity"]}
        if result.match_type == MatchType.VERIFIED and normalized_requirement not in existing:
            group["verified"].append(result.requirement)
        elif result.match_type == MatchType.FAMILIARITY and normalized_requirement not in existing:
            group["familiarity"].append(result.requirement)
        elif result.match_type == MatchType.TRANSFERABLE and wording not in group["related"]:
            group["related"].append(wording)
        elif result.match_type == MatchType.MISSING and normalized_requirement not in existing:
            group["verified"].append(result.requirement)
        group["relevance"] += 10
    tailored_experience = []
    for experience in profile.experience:
        responsibilities = sorted(
            experience.responsibilities,
            key=relevance_score,
            reverse=True,
        )
        achievements = sorted(
            experience.achievements,
            key=relevance_score,
            reverse=True,
        )
        tailored_experience.append(experience.model_copy(update={
            "responsibilities": responsibilities,
            "achievements": achievements,
        }))

    tailored = profile.model_copy(update={
        "experience": tailored_experience[:settings.max_experience_entries],
        "projects": sorted(profile.projects, key=rank, reverse=True)[:settings.max_project_entries],
        "skills": cv_skills,
    })
    return env.get_template("default_cv.tex.j2").render(candidate=tailored, job=job, match=match, skill_groups=skill_groups)


def generate_change_log(match: MatchAnalysis) -> str:
    rows = ["# Change log", "", "Tailoring uses only entries in the candidate master profile.", "", "## Emphasized"]
    rows.extend(f"- {m.requirement}: {m.recommended_wording}" for m in match.matches if m.match_type in (MatchType.VERIFIED, MatchType.TRANSFERABLE, MatchType.FAMILIARITY))
    rows += ["", "## Not claimed"]
    rows.extend(f"- {m.requirement}: no supporting profile evidence." for m in match.matches if m.match_type == MatchType.MISSING)
    return "\n".join(rows) + "\n"


def validate_generated_text(text: str, profile: CandidateProfile, match: MatchAnalysis) -> dict:
    normalized = text.casefold()
    unsupported = [m.requirement for m in match.matches if m.match_type == MatchType.MISSING and _unsupported_positive_claim(text, m.requirement)]
    overclaims = []
    for skill in profile.skills:
        if skill.status.value != "FAMILIARITY": continue
        start = normalized.find(skill.name.casefold())
        if start < 0: continue
        near = normalized[max(0, start - 80):start + len(skill.name) + 80]
        if any(term in near for term in ("expert", "professional experience", "developed", "led", "implemented")): overclaims.append(skill.name)
    warnings = [f"Unsupported requirement may have been mentioned: {name}" for name in unsupported]
    issues = [f"Unsupported requirement presented as experience: {name}" for name in unsupported]
    issues.extend(f"Familiarity may be overstated: {name}" for name in overclaims)
    return {"passed": not issues, "issues": issues, "warnings": warnings, "unsupported_claims": unsupported + overclaims,
            "missing_requirements": [m.requirement for m in match.matches if m.match_type == MatchType.MISSING]}


def _unsupported_positive_claim(text: str, requirement: str) -> bool:
    """Return true only when a missing requirement is presented as experience.

    Honest statements such as "I have not used MPTCP yet" or "I would like to
    learn MPTCP" are not overclaims. The generated letter still should not
    mention gaps unnecessarily, but they should not trigger a factuality error.
    """
    normalized = text.casefold()
    target = requirement.casefold().strip()
    start = normalized.find(target)
    if len(target) <= 2 or start < 0:
        return False
    context = normalized[max(0, start - 140):start + len(target) + 100]
    non_claim_markers = (
        "not used", "haven't used", "have not used", "without experience",
        "no direct experience", "not yet", "would like to learn", "want to learn",
        "hope to learn", "develop familiarity", "study", "learning",
    )
    if any(marker in context for marker in non_claim_markers):
        return False

    # Merely naming a job need is not a fabrication. Require language that
    # actually attributes the requirement to the candidate before blocking it.
    claim_markers = (
        "i have", "i used", "i worked with", "i developed", "i implemented",
        "i have developed", "i have implemented", "i have used", "i have worked with",
        "i designed", "i built", "i managed", "i led", "my experience with",
        "my work with", "experience in", "background in", "proficient in",
        "expertise in", "familiar with",
    )
    target_start = context.find(target)
    prefix = context[:target_start]
    sentence_start = max(prefix.rfind(".") + 1, prefix.rfind("!") + 1, prefix.rfind("?") + 1)
    sentence = context[sentence_start:]
    return any(marker in sentence for marker in claim_markers)


def generate_letter_tex(
    letter: str,
    candidate: CandidateProfile,
    company: str = "",
    position: str = "",
) -> str:
    """Render a cover letter into the company-headed LaTeX template."""
    env = Environment(loader=FileSystemLoader(ROOT / "templates" / "cover_letter"))
    env.filters["latex_escape"] = lambda value: (
        str(value)
        .replace("\\", r"\textbackslash{}")
        .replace("&", r"\&")
        .replace("%", r"\%")
        .replace("$", r"\$")
        .replace("#", r"\#")
        .replace("_", r"\_")
        .replace("{", r"\{")
        .replace("}", r"\}")
    )
    paragraphs = [paragraph.strip() for paragraph in letter.split("\n\n") if paragraph.strip()]
    return env.get_template("default_cover_letter.tex.j2").render(
        candidate=candidate,
        company=company.strip() or "Company not specified",
        position=position.strip(),
        paragraphs=paragraphs,
    )


def company_document_stem(company: str, document_type: str) -> str:
    """Build a safe, readable company-specific document download stem."""
    from werkzeug.utils import secure_filename

    safe_company = " ".join(secure_filename(company or "Company").replace("_", " ").split()) or "Company"
    safe_type = " ".join(secure_filename(document_type or "Document").replace("_", " ").split()) or "Document"
    return f"{safe_company} {safe_type}"


def compile_pdf(tex_path: Path) -> Path:
    import shutil, subprocess
    compiler = shutil.which("latexmk") or shutil.which("pdflatex")
    if not compiler:
        raise RuntimeError("No LaTeX compiler found. Install latexmk or pdflatex to create PDFs; the .tex file was saved.")
    args = [compiler, "-pdf", "-interaction=nonstopmode", tex_path.name] if Path(compiler).name == "latexmk" else [compiler, "-interaction=nonstopmode", tex_path.name]
    run = subprocess.run(args, cwd=tex_path.parent, text=True, capture_output=True)
    pdf = tex_path.with_suffix(".pdf")
    if run.returncode or not pdf.exists():
        raise RuntimeError((run.stdout + "\n" + run.stderr)[-5000:])
    return pdf
