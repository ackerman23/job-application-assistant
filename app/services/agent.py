"""Verify -> critique -> revise loop for generated cover letters.

Deterministic guardrails (regex fact checks, style report) always run and take
priority. Model-based checks add semantic coverage and degrade gracefully: if a
checker call fails, the loop continues with the deterministic checks only.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from app.core.config import CRITIC_MODEL, VALIDATION_MODEL
from app.models.schemas import CandidateProfile, JobAnalysis, MatchAnalysis
from app.services.cover_letter_engine import CoverLetterIntelligenceEngine
from app.services.llm import complete_json

MAX_REVISIONS = 2
PASS_SCORE = 80

FACT_CHECK_PROMPT = """You are a strict fact checker for a job application letter. Compare the letter only against the supplied candidate profile, applicant notes and verified_company_research (quotes from the company's own pages, which support statements about the company). List every claim in the letter (skills, tools, employers, projects, outcomes, metrics, dates, motivations, company knowledge) that the evidence does not support, and every place where FAMILIARITY or MISSING skills are presented as real experience. Search every part of the profile before flagging: skills and their evidence, experience, projects, achievements, education, and the applicant notes; a claim is supported if any of them states or clearly implies it, even in different words. Statements of enthusiasm, interest, motivation or career goals are not factual claims, and neither are honest statements of a learning goal or a gap. Do not flag a requirement that is merely named as the job's need. Return one JSON object: {"unsupported_claims": [{"claim": str, "reason": str}]}. Return an empty list when everything is supported."""

CRITIC_PROMPT = """You are a demanding technical recruiter reading a cover letter for the supplied role. Judge specificity to the role, use of concrete candidate evidence, natural tone, and generic or filler phrasing. Do not reward claims; do not suggest adding facts that are not in the candidate evidence. Return one JSON object: {"score": integer 0-100, "issues": [str], "revision_instructions": [str]}. Keep issues short and actionable."""


@dataclass
class Round:
    revision: int
    fact_issues: list[str]
    critique_score: int | None
    style_issues: list[str]
    critique_issues: list[str]

    @property
    def passed(self) -> bool:
        return not self.fact_issues and (self.critique_score is None or self.critique_score >= PASS_SCORE) and not self.style_issues


@dataclass
class RefinementResult:
    text: str
    rounds: list[Round] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def revisions(self) -> int:
        return max(0, len(self.rounds) - 1)


def _evidence_payload(profile: CandidateProfile, match: MatchAnalysis, applicant_notes: str, company_research: dict | None = None) -> dict:
    payload = {
        "candidate_profile": profile.model_dump(mode="json"),
        "applicant_notes": applicant_notes,
        "requirement_assessment": [
            {"requirement": m.requirement, "status": m.match_type.value, "evidence": m.candidate_evidence}
            for m in match.matches
        ],
    }
    if company_research:
        payload["verified_company_research"] = company_research
    return payload


def _fact_issues(text: str, profile: CandidateProfile, match: MatchAnalysis, applicant_notes: str, notes: list[str], company_research: dict | None = None) -> list[str]:
    from app.services.generation import validate_generated_text

    issues = list(validate_generated_text(text, profile, match)["issues"])
    issues.extend(
        f"Unsupported claim: {c}" for c in CoverLetterIntelligenceEngine().validate_facts(text, profile, match).unsupported_claims
        if f"Unsupported requirement presented as experience: {c}" not in issues
    )
    try:
        result = complete_json(
            FACT_CHECK_PROMPT,
            {**_evidence_payload(profile, match, applicant_notes, company_research), "letter": text},
            model=VALIDATION_MODEL,
        )
        for row in result.get("unsupported_claims", []) or []:
            if isinstance(row, dict) and row.get("claim"):
                issues.append(f"Unsupported claim: {row['claim']} ({row.get('reason', 'no supporting evidence')})")
    except Exception as exc:
        notes.append(f"Model fact check unavailable ({type(exc).__name__}); only rule-based checks ran.")
    return issues


def _critique(text: str, job: JobAnalysis, profile: CandidateProfile, notes: list[str]) -> tuple[int | None, list[str], list[str]]:
    try:
        result = complete_json(
            CRITIC_PROMPT,
            {
                "role": job.position,
                "company": job.company,
                "required_skills": job.required_skills,
                "candidate_evidence": profile.model_dump(mode="json"),
                "letter": text,
            },
            model=CRITIC_MODEL,
        )
        score = max(0, min(100, int(result.get("score", 0))))
        issues = [str(x) for x in result.get("issues", []) or []]
        fixes = [str(x) for x in result.get("revision_instructions", []) or []]
        return score, issues, fixes
    except Exception as exc:
        notes.append(f"Recruiter critique unavailable ({type(exc).__name__}); only rule-based style checks ran.")
        return None, [], []


def refine_cover_letter(
    draft: str,
    *,
    profile: CandidateProfile,
    job: JobAnalysis,
    match: MatchAnalysis,
    applicant_notes: str,
    revise: Callable[[str, list[str]], str],
    company_research: dict | None = None,
    max_revisions: int = MAX_REVISIONS,
) -> RefinementResult:
    """Return the best letter found within the revision budget.

    Candidates are ranked by fact issues first, then critique score, so a stylistic
    gain can never be bought with an unsupported claim. Remaining problems are
    returned as warnings instead of being hidden.
    """
    engine = CoverLetterIntelligenceEngine()
    notes: list[str] = []
    result = RefinementResult(text=draft)
    best: tuple[tuple[int, int], str, Round] | None = None
    text = draft

    for revision in range(max_revisions + 1):
        facts = _fact_issues(text, profile, match, applicant_notes, notes, company_research)
        quality = engine.quality_report(text, job, match)
        style = list(quality.generic_phrases)
        score, critique_issues, fixes = _critique(text, job, profile, notes)
        current = Round(revision, facts, score, style, critique_issues)
        result.rounds.append(current)

        rank = (len(facts), -(score if score is not None else 50))
        if best is None or rank < best[0]:
            best = (rank, text, current)
        if current.passed:
            break
        if revision == max_revisions:
            break

        instructions = [f"Remove or soften (no evidence): {issue}" for issue in facts]
        instructions += [f"Replace generic phrase: {phrase}" for phrase in style]
        instructions += critique_issues + fixes
        try:
            revised = revise(text, instructions)
        except Exception as exc:
            notes.append(f"Revision call failed ({type(exc).__name__}); keeping the best draft so far.")
            break
        if not revised or not revised.strip() or revised.strip() == text.strip():
            break
        text = revised

    assert best is not None
    result.text = best[1]
    final = best[2]
    result.warnings = list(dict.fromkeys(
        [*final.fact_issues, *(f"Style: {s}" for s in final.style_issues), *notes]
    ))
    return result


def format_trace(result: RefinementResult) -> str:
    return json.dumps(
        [
            {"revision": r.revision, "fact_issues": r.fact_issues, "score": r.critique_score, "style": r.style_issues}
            for r in result.rounds
        ],
        ensure_ascii=False,
    )
