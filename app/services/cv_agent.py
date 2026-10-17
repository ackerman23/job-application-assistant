"""Evidence-bound CV tailoring: plan -> validate -> verify -> coverage check -> re-plan.

The model may reorder bullets and lightly reword them to use the job's own
terminology, but it never gets to add facts. Every rewrite must pass
deterministic checks and an independent faithfulness check; anything that fails
reverts to the candidate's original wording. Skills the user explicitly selects
as "missing" are handled elsewhere (skills section only) and are blocked from
appearing in rewritten experience bullets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.config import OPENAI_API_KEY, VALIDATION_MODEL, WRITING_MODEL
from app.models.schemas import CandidateProfile, JobAnalysis, MatchAnalysis, MatchType
from app.services.llm import complete_json

MAX_REPLANS = 1

PLAN_PROMPT = """You tailor a CV to one job using only the candidate's existing bullets. You receive each experience and project with its bullets (each has an id such as r0 for responsibilities and a0 for achievements), the job's requirements with importance and the candidate's evidence status, and a list of requirements that are MISSING.

For every experience and project return the bullets to show, most relevant to the job first. You may reword a bullet only to use the job's own terminology for something the original bullet already states, to lead with the strongest relevant action, or to tighten wording. Hard rules: never add a fact, tool, technology, number, metric, outcome, scope, or team size that is not in that bullet; never merge two bullets; never mention any MISSING requirement; keep a rewrite in the same language as the original and no more than 1.3 times its length; if a bullet is not relevant, keep it later in the order rather than inventing relevance. If you do not need to change a bullet, return its original text unchanged. Reference bullets by their id in "source".

Return one JSON object: {"experience": [{"index": int, "responsibilities": [{"source": str, "text": str}], "achievements": [{"source": str, "text": str}]}], "projects": [same shape with "index"]}."""

VERIFY_PROMPT = """You are a strict faithfulness checker for CV bullets. For each item compare the rewrite with the original bullet (and the entry's listed technologies). The rewrite is faithful only if it states nothing the original does not: no new tool, technology, number, metric, outcome, scope, responsibility, or seniority. Rewording, reordering, and terminology alignment for the same thing are allowed. Return one JSON object {"unfaithful": [id, ...]} listing the ids of rewrites that are not faithful. Return an empty list if all are faithful."""


@dataclass
class CVReport:
    rewrites_accepted: int = 0
    rewrites_rejected: int = 0
    replans: int = 0
    coverage_percent: int | None = None
    uncovered: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        rows = ["## CV tailoring report", ""]
        rows.append(f"- Bullets reworded and verified: {self.rewrites_accepted}")
        rows.append(f"- Rewrites rejected (original kept): {self.rewrites_rejected}")
        if self.coverage_percent is not None:
            rows.append(f"- Important supported requirements visible in the CV: {self.coverage_percent}%")
        rows.extend(f"- Not visible anywhere in the CV: {item}" for item in self.uncovered)
        rows.extend(f"- {note}" for note in self.notes)
        return "\n".join(rows) + "\n"


class CVDocument(str):
    """CV LaTeX source that also carries the tailoring report."""

    def __new__(cls, text: str, report: CVReport | None = None):
        obj = super().__new__(cls, text)
        obj.report = report or CVReport()
        return obj


def _words(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#]+", value.casefold()))


def _contains_term(text: str, term: str) -> bool:
    term = term.strip().casefold()
    return bool(term) and re.search(r"(?<![\w+#])" + re.escape(term) + r"(?![\w+#])", text.casefold()) is not None


def _bullet_catalog(profile: CandidateProfile) -> tuple[list[dict], list[dict]]:
    def entry(index, label, responsibilities, achievements, technologies):
        return {
            "index": index,
            "label": label,
            "technologies": technologies,
            "responsibilities": [{"id": f"r{i}", "text": t} for i, t in enumerate(responsibilities)],
            "achievements": [{"id": f"a{i}", "text": t} for i, t in enumerate(achievements)],
        }

    experience = [
        entry(i, f"{e.role} at {e.company}", e.responsibilities, e.achievements, e.technologies)
        for i, e in enumerate(profile.experience)
    ]
    projects = [
        entry(i, p.name, p.responsibilities, p.achievements, p.technologies)
        for i, p in enumerate(profile.projects)
    ]
    return experience, projects


def _requirement_payload(match: MatchAnalysis, selected: set[str]) -> dict:
    return {
        "requirements": [
            {
                "requirement": m.requirement,
                "importance": m.importance,
                "status": m.match_type.value,
                "supporting_evidence": m.candidate_evidence[:3],
                "user_selected": m.requirement.casefold() in selected,
            }
            for m in match.matches
            if m.match_type != MatchType.CONFLICT
        ],
        "missing_requirements_never_mention": [m.requirement for m in match.matches if m.match_type == MatchType.MISSING],
    }


def _validate_rewrite(original: str, rewrite: str, blocked_terms: list[str]) -> bool:
    rewrite = rewrite.strip()
    if not rewrite or len(rewrite) > max(int(len(original) * 1.3), len(original) + 40):
        return False
    if not set(re.findall(r"\d+(?:[.,]\d+)?", rewrite)) <= set(re.findall(r"\d+(?:[.,]\d+)?", original)):
        return False
    return not any(_contains_term(rewrite, term) and not _contains_term(original, term) for term in blocked_terms)


def _resolve_entry(
    originals: dict[str, str],
    planned: list,
    kind: str,
    blocked_terms: list[str],
    max_bullets: int,
    pending: list[dict],
    entry_key: str,
) -> list[tuple[str, str | None]]:
    """Return ordered (original_id, rewrite_or_None) pairs for one bullet group."""
    ordered: list[tuple[str, str | None]] = []
    used: set[str] = set()
    for row in planned if isinstance(planned, list) else []:
        if not isinstance(row, dict):
            continue
        source = str(row.get("source", ""))
        if source not in originals or source in used or not source.startswith(kind):
            continue
        used.add(source)
        text = str(row.get("text", "")).strip()
        original = originals[source]
        if text and text != original and _validate_rewrite(original, text, blocked_terms):
            pending.append({"id": f"{entry_key}.{source}", "original": original, "rewrite": text})
            ordered.append((source, text))
        else:
            ordered.append((source, None))
    ordered.extend((source, None) for source in originals if source not in used)
    return ordered[:max_bullets]


def _plan_once(
    profile: CandidateProfile,
    job: JobAnalysis,
    match: MatchAnalysis,
    selected: set[str],
    max_bullets: int,
    hints: list[str],
    report: CVReport,
) -> tuple[list, list] | None:
    experience, projects = _bullet_catalog(profile)
    payload = {
        "job": {"role": job.position, "company": job.company, "responsibilities": job.responsibilities},
        **_requirement_payload(match, selected),
        "max_bullets_per_entry": max_bullets,
        "experience": experience,
        "projects": projects,
        "coverage_hints": hints,
    }
    try:
        plan = complete_json(PLAN_PROMPT, payload, model=WRITING_MODEL)
    except Exception as exc:
        report.notes.append(f"AI tailoring unavailable ({type(exc).__name__}); bullets were ordered by keyword relevance only.")
        return None

    blocked = [m.requirement for m in match.matches if m.match_type == MatchType.MISSING]
    pending: list[dict] = []
    plan_exp = {r.get("index"): r for r in plan.get("experience", []) if isinstance(r, dict)}
    plan_prj = {r.get("index"): r for r in plan.get("projects", []) if isinstance(r, dict)}

    def build(entries, items, planned_by_index, prefix):
        out = []
        for position, item in enumerate(entries):
            row = planned_by_index.get(position, {})
            responsibilities = {f"r{i}": t for i, t in enumerate(item.responsibilities)}
            achievements = {f"a{i}": t for i, t in enumerate(item.achievements)}
            key = f"{prefix}{position}"
            out.append((
                _resolve_entry(responsibilities, row.get("responsibilities"), "r", blocked, max_bullets, pending, key),
                _resolve_entry(achievements, row.get("achievements"), "a", blocked, max_bullets, pending, key),
                responsibilities,
                achievements,
            ))
        return out

    built_exp = build(profile.experience, experience, plan_exp, "e")
    built_prj = build(profile.projects, projects, plan_prj, "p")

    rejected: set[str] = set()
    if pending:
        technologies = {f"e{i}": e.technologies for i, e in enumerate(profile.experience)}
        technologies.update({f"p{i}": p.technologies for i, p in enumerate(profile.projects)})
        try:
            verdict = complete_json(
                VERIFY_PROMPT,
                {"items": [{**row, "technologies": technologies.get(row["id"].split(".")[0], [])} for row in pending]},
                model=VALIDATION_MODEL,
            )
            rejected = {str(x) for x in verdict.get("unfaithful", []) or []}
        except Exception as exc:
            # Fail closed: without an independent check, no rewrite is trusted.
            rejected = {row["id"] for row in pending}
            report.notes.append(f"Faithfulness check unavailable ({type(exc).__name__}); original bullet wording was kept.")
    report.rewrites_accepted += len(pending) - len(rejected)
    report.rewrites_rejected += len(rejected)

    def realise(prefix, built):
        result = []
        for position, (resp, ach, resp_orig, ach_orig) in enumerate(built):
            key = f"{prefix}{position}"
            def pick(pairs, originals):
                return [
                    (rewrite if rewrite is not None and f"{key}.{source}" not in rejected else originals[source])
                    for source, rewrite in pairs
                ]
            result.append((pick(resp, resp_orig), pick(ach, ach_orig)))
        return result

    return realise("e", built_exp), realise("p", built_prj)


def _coverage(match: MatchAnalysis, texts: list[str]) -> tuple[int | None, list[str]]:
    body = " ".join(texts).casefold()
    body_words = _words(body)
    supported = [
        m for m in match.matches
        if m.importance in {"HIGH", "MEDIUM"} and m.match_type in (MatchType.VERIFIED, MatchType.TRANSFERABLE)
    ]
    if not supported:
        return None, []
    uncovered = []
    for m in supported:
        words = _words(m.requirement)
        if not (_contains_term(body, m.requirement) or (words and words <= body_words)):
            uncovered.append(m.requirement)
    return round(100 * (len(supported) - len(uncovered)) / len(supported)), uncovered


def tailor_profile(
    profile: CandidateProfile,
    job: JobAnalysis,
    match: MatchAnalysis,
    selected_requirements: list[str] | None,
    max_bullets: int = 6,
) -> tuple[CandidateProfile, CVReport]:
    """Return a profile whose bullets are ordered, trimmed, and verified for this job."""
    report = CVReport()
    if not OPENAI_API_KEY:
        return profile, report

    selected = {s.casefold() for s in (selected_requirements or [])}
    hints: list[str] = []
    plan = None
    for attempt in range(MAX_REPLANS + 1):
        report.rewrites_accepted = report.rewrites_rejected = 0
        plan = _plan_once(profile, job, match, selected, max_bullets, hints, report)
        if plan is None:
            return profile, report
        texts = [t for group in (*plan[0], *plan[1]) for part in group for t in part]
        texts += [skill.name for skill in profile.skills]
        texts += [tech for entry in (*profile.experience, *profile.projects) for tech in entry.technologies]
        coverage, uncovered = _coverage(match, texts)
        report.coverage_percent, report.uncovered = coverage, uncovered
        if not uncovered or attempt == MAX_REPLANS:
            break
        report.replans += 1
        hints = [
            f"'{m.requirement}' ({m.importance}) is supported by: {' | '.join(m.candidate_evidence[:2])}. Lead with the bullet that shows it, if one does."
            for m in match.matches if m.requirement in uncovered
        ]

    experience = [
        e.model_copy(update={"responsibilities": resp, "achievements": ach})
        for e, (resp, ach) in zip(profile.experience, plan[0])
    ]
    projects = [
        p.model_copy(update={"responsibilities": resp, "achievements": ach})
        for p, (resp, ach) in zip(profile.projects, plan[1])
    ]
    return profile.model_copy(update={"experience": experience, "projects": projects}), report
