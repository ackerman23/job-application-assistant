import re
from app.models.schemas import CandidateProfile, JobAnalysis, MatchAnalysis, RequirementMatch, MatchType
from app.core.config import OPENAI_API_KEY
from app.services.llm import complete_json

NON_TECHNICAL_REQUIREMENT_PATTERNS = (
    r"\bcommunication skills?\b",
    r"\bcommunication\b(?!\s+(?:protocols?|interfaces?|systems?|networks?))",
    r"\bverbal communication\b",
    r"\bwritten communication\b",
    r"\binterpersonal skills?\b",
    r"\bteamwork\b",
    r"\bteam player\b",
    r"\bcollaboration skills?\b",
    r"\bcollaborat(?:ion|ive)\b",
    r"\bstakeholder management\b",
    r"\bleadership skills?\b",
    r"\bleadership\b",
    r"\bproblem[- ]solving skills?\b",
    r"\btime management\b",
    r"\borganizational skills?\b",
    r"\borganization(?:al)?\b",
    r"\battention to detail\b",
    r"\bself[- ]motivated\b",
    r"\bfast[- ]paced\b",
    r"\bwork under pressure\b",
    r"\binterpersonal\b",
    r"\bteam-oriented\b",
    r"\bproactive attitude\b",
    r"\bstrong written and verbal\b",
    r"\bexcellent written and verbal\b",
)


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#]+", value.lower()))


def _profile_evidence(profile: CandidateProfile):
    rows = []
    for skill in profile.skills:
        rows.append((skill.name, skill.status.value, "; ".join(skill.evidence) or f"Profile skill: {skill.name}"))
    for exp in profile.experience:
        for value in [*exp.technologies, *exp.domains, exp.role, *exp.responsibilities, *exp.achievements]:
            rows.append((value, exp.evidence_level.value, f"{exp.role} at {exp.company}: {value}"))
    for project in profile.projects:
        for value in [*project.technologies, *project.domain, *project.relevance_tags, *project.responsibilities, *project.achievements, project.description]:
            rows.append((value, "VERIFIED", f"{project.name}: {value}"))
    return rows


def _similarity(requirement: str, evidence: str) -> float:
    a, b = _tokens(requirement), _tokens(evidence)
    if not a or not b: return 0
    overlap = len(a & b) / len(a)
    aliases = {"postgresql": "database", "sql": "database", "gds": "satellite", "telemetry": "satellite", "ground": "satellite", "validation": "testing", "sysml": "systems", "mbse": "systems"}
    expanded_a = a | {aliases[x] for x in a if x in aliases}
    expanded_b = b | {aliases[x] for x in b if x in aliases}
    return max(overlap, len(expanded_a & expanded_b) / len(expanded_a))


def _job_skill_requirements(job: JobAnalysis) -> list[str]:
    raw = job.required_skills + job.preferred_skills + job.technical_skills + job.domain_keywords + job.tools_and_technologies + job.implicit_requirements
    excluded_phrases = ("interest in", "ability to", "commitment to", "enrolled full", "fluent in", "creative solutions", "developing yourself", "explore and elaborate", "compliance risk", "act with integrity")
    return list(dict.fromkeys(value.strip() for value in raw if value.strip()
        and len(value.split()) <= 8
        and not any(phrase in value.casefold() for phrase in excluded_phrases)
        and not any(re.search(pattern, value, re.I) for pattern in NON_TECHNICAL_REQUIREMENT_PATTERNS)))


def _match_job_local(job: JobAnalysis, profile: CandidateProfile) -> MatchAnalysis:
    evidence = _profile_evidence(profile)
    requirements = _job_skill_requirements(job)
    matches = []
    for req in requirements:
        ranked = sorted((( _similarity(req, value), value, level, ev) for value, level, ev in evidence), reverse=True)
        direct = [x for x in ranked if x[0] >= 0.75]
        related = [x for x in ranked if 0.30 <= x[0] < 0.75]
        if direct:
            selected = direct[:4]
            familiarity = all(x[2] == "FAMILIARITY" for x in selected)
            kind = MatchType.FAMILIARITY if familiarity else MatchType.VERIFIED
            wording = f"Familiarity with {req}" if familiarity else req
        elif related:
            selected = related[:3]; kind = MatchType.TRANSFERABLE
            wording = "Related experience with " + ", ".join(dict.fromkeys(x[1] for x in selected))
        else:
            selected = []; kind = MatchType.MISSING; wording = ""
        importance = "HIGH" if req in job.required_skills else ("LOW" if req in job.preferred_skills else "MEDIUM")
        matches.append(RequirementMatch(requirement=req, importance=importance, match_type=kind,
            candidate_evidence=[x[3] for x in selected], recommended_wording=wording,
            confidence=round(selected[0][0], 2) if selected else 0.0))
    weights = {MatchType.VERIFIED: 1, MatchType.TRANSFERABLE: .6, MatchType.FAMILIARITY: .35, MatchType.MISSING: 0, MatchType.CONFLICT: 0}
    score = round(100 * sum(weights[m.match_type] for m in matches) / max(1, len(matches)))
    summary = f"Evidence-backed coverage across {len(matches)} extracted requirements. Match score: {score}%." if matches else "No requirements were extracted; provide a more complete job description."
    learning = [{"skill": m.requirement, "current_status": "MISSING", "priority": m.importance, "reason": "No supporting evidence was found in the master profile.", "recommended_learning": "Review introductory material and complete a small practical exercise before describing this as familiarity."} for m in matches if m.match_type == MatchType.MISSING]
    return MatchAnalysis(matches=matches, score=score, summary=summary, learning_recommendations=learning)


def _match_job_ai(job: JobAnalysis, profile: CandidateProfile) -> MatchAnalysis:
    evidence = _profile_evidence(profile)
    requirements = _job_skill_requirements(job)
    payload = {
        "job": job.model_dump(mode="json"),
        "requirements_to_assess": requirements,
        "candidate_evidence": [{"id": i, "status": status, "content": content} for i, (_, status, content) in enumerate(evidence)],
    }
    prompt = """Compare every supplied technical skill, engineering domain, or tool requirement against only the candidate evidence records. Return a JSON object with keys matches, summary, learning_recommendations. For each requirement return requirement (exact input text), importance (HIGH/MEDIUM/LOW), match_type (VERIFIED/TRANSFERABLE/FAMILIARITY/MISSING), evidence_indices (array of supplied record IDs), recommended_wording (short and truthful), confidence (0..1). Use VERIFIED only when the cited evidence directly supports it; TRANSFERABLE only when cited adjacent evidence exists; FAMILIARITY only for evidence marked FAMILIARITY; otherwise MISSING. Never infer an experience, tool, outcome, metric, or qualification. A missing technical skill may be named as a learning priority but not as candidate experience. Return one assessment per input requirement. Learning recommendations should be specific to the job and clearly distinguish current state from what to learn. Do not add or assess generic soft skills or personal traits such as communication, teamwork, leadership, interpersonal skills, stakeholder management, organization, or time management; those are outside this technical review."""
    result = complete_json(prompt, payload)
    raw_matches = result.get("matches")
    if not isinstance(raw_matches, list):
        raise ValueError("AI response omitted the matches list")
    evidence_by_id = {i: (value, status, source) for i, (value, status, source) in enumerate(evidence)}
    by_requirement = {str(row.get("requirement", "")).casefold(): row for row in raw_matches if isinstance(row, dict)}
    matches = []
    for req in requirements:
        row = by_requirement.get(req.casefold())
        if not row:
            continue
        try:
            kind = MatchType(str(row.get("match_type", "MISSING")).upper())
        except ValueError:
            kind = MatchType.MISSING
        ids = row.get("evidence_indices", [])
        selected = [evidence_by_id[i] for i in ids if isinstance(i, int) and i in evidence_by_id] if isinstance(ids, list) else []
        if kind == MatchType.FAMILIARITY and (not selected or any(x[1] != "FAMILIARITY" for x in selected)):
            kind = MatchType.MISSING if not selected else MatchType.VERIFIED
        if kind in (MatchType.VERIFIED, MatchType.TRANSFERABLE) and not selected:
            kind = MatchType.MISSING
        if kind == MatchType.VERIFIED and selected and all(x[1] == "FAMILIARITY" for x in selected):
            kind = MatchType.FAMILIARITY
        if kind == MatchType.MISSING:
            selected = []
        wording = str(row.get("recommended_wording", ""))[:500] if kind != MatchType.MISSING else ""
        try:
            confidence = max(0.0, min(1.0, float(row.get("confidence", 0.0))))
        except (ValueError, TypeError):
            confidence = 0.0
        importance = str(row.get("importance", "MEDIUM")).upper()
        if importance not in {"HIGH", "MEDIUM", "LOW"}:
            importance = "MEDIUM"
        matches.append(RequirementMatch(requirement=req, importance=importance, match_type=kind,
            candidate_evidence=[x[2] for x in selected[:5]], recommended_wording=wording, confidence=confidence))
    if len(matches) != len(requirements):
        raise ValueError("AI did not return an assessment for every requirement")
    weights = {MatchType.VERIFIED: 1, MatchType.TRANSFERABLE: .6, MatchType.FAMILIARITY: .35, MatchType.MISSING: 0, MatchType.CONFLICT: 0}
    score = round(100 * sum(weights[m.match_type] for m in matches) / max(1, len(matches)))
    learning = result.get("learning_recommendations", [])
    if not isinstance(learning, list): learning = []
    learning = [x for x in learning if isinstance(x, dict) and x.get("skill")]
    summary = str(result.get("summary", ""))[:1000] or f"AI assessed {len(matches)} job requirements against profile evidence. Match score: {score}%."
    return MatchAnalysis(analysis_method="AI-assisted", matches=matches, score=score, summary=summary,
        learning_recommendations=[{str(k): str(v) for k, v in item.items()} for item in learning])


def match_job(job: JobAnalysis, profile: CandidateProfile) -> MatchAnalysis:
    """Use model-assisted evidence matching when configured, with deterministic fallback."""
    if OPENAI_API_KEY:
        try:
            return _match_job_ai(job, profile)
        except Exception as exc:
            fallback = _match_job_local(job, profile)
            return fallback.model_copy(update={
                "analysis_method": "local fallback",
                "analysis_warning": f"AI matching failed ({type(exc).__name__}); local matching is shown instead.",
            })
    return _match_job_local(job, profile)
