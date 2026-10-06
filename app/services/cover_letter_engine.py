"""Structured, evidence-first stages used by cover-letter generation."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.models.schemas import (
    ApplicationStrategy,
    CandidateNarrative,
    CandidateProfile,
    CoverLetterQualityReport,
    CompanyResearch,
    EvidenceRecord,
    EvidenceLevel,
    HiringNeedAnalysis,
    JobAnalysis,
    JobUnderstanding,
    MatchAnalysis,
    MatchType,
    RoleIntersection,
    RecruiterCritique,
    FactValidation,
    VoiceProfile,
)


@dataclass(frozen=True)
class CoverLetterResearch:
    """Public facts available from the supplied job material.

    External company research is deliberately empty unless a verified research
    provider is added. The engine must never turn a company name into invented
    company knowledge.
    """

    verified_facts: tuple[str, ...] = ()
    proprietary_unknowns: tuple[str, ...] = ()

    def as_model(self) -> CompanyResearch:
        return CompanyResearch(
            company_context=list(self.verified_facts),
            candidate_relevant_points=list(self.verified_facts),
            verified=bool(self.verified_facts),
        )


class CoverLetterIntelligenceEngine:
    """Build structured context before the final prose-generation call."""

    def understand_job(self, job: JobAnalysis) -> JobUnderstanding:
        activities = list(dict.fromkeys(job.likely_daily_activities or job.responsibilities))
        return JobUnderstanding(
            concrete_activities=activities,
            technical_needs=list(dict.fromkeys(job.technical_skills + job.tools_and_technologies)),
            domain_needs=list(dict.fromkeys(job.domain_keywords)),
            learning_expectations=list(dict.fromkeys(job.preferred_skills)),
            implicit_needs=list(dict.fromkeys(job.implicit_requirements)),
            source_requirements={
                "responsibilities": list(job.responsibilities),
                "required": list(job.required_skills),
                "preferred": list(job.preferred_skills),
            },
        )

    def identify_hiring_need(self, job: JobAnalysis, understanding: JobUnderstanding) -> HiringNeedAnalysis:
        needs = understanding.technical_needs + understanding.domain_needs
        core = "A candidate who can contribute to " + ", ".join(needs[:3]) if needs else "A candidate who can contribute to the documented responsibilities of this role."
        return HiringNeedAnalysis(
            core_hiring_need=core,
            technical_needs=understanding.technical_needs,
            domain_needs=understanding.domain_needs,
            working_style_needs=[value for value in job.soft_skills if value],
            learning_expectations=understanding.learning_expectations,
            implicit_needs=understanding.implicit_needs,
        )

    def research_company(self, job: JobAnalysis) -> CoverLetterResearch:
        facts = tuple(value for value in (job.company, job.position, job.location, job.employment_type) if value)
        return CoverLetterResearch(verified_facts=facts)

    def accept_verified_research(self, research: CompanyResearch | None) -> CompanyResearch:
        """Accept caller-supplied research without pretending to verify it."""
        if research is None:
            return CompanyResearch()
        if not research.verified:
            return CompanyResearch()
        return research

    def retrieve_evidence(self, profile: CandidateProfile) -> list[EvidenceRecord]:
        records: list[EvidenceRecord] = []
        for experience in profile.experience:
            source = f"{experience.role} at {experience.company}".strip(" at")
            for claim in [*experience.evidence, *experience.responsibilities, *experience.achievements, *experience.technologies, *experience.domains]:
                if claim:
                    records.append(EvidenceRecord(claim=claim, evidence=claim, source=source, evidence_level=experience.evidence_level, relevance_tags=experience.domains))
        for project in profile.projects:
            source = project.name or "Candidate project"
            for claim in [project.description, *project.responsibilities, *project.achievements, *project.technologies, *project.domain]:
                if claim:
                    records.append(EvidenceRecord(claim=claim, evidence=claim, source=source, evidence_level=EvidenceLevel.VERIFIED, relevance_tags=project.relevance_tags or project.domain))
        for skill in profile.skills:
            for evidence in skill.evidence or [skill.name]:
                records.append(EvidenceRecord(claim=skill.name, evidence=evidence, source="Master profile skill", evidence_level=skill.status))
        return records

    def find_intersections(self, match: MatchAnalysis) -> list[RoleIntersection]:
        return [
            RoleIntersection(
                job_need=item.requirement,
                candidate_evidence="; ".join(item.candidate_evidence),
                strength="HIGH" if item.match_type == MatchType.VERIFIED else "MEDIUM",
                recommended_use=item.recommended_wording,
                why_relevant=item.recommended_wording or f"This evidence is related to {item.requirement}.",
                possible_letter_use=item.recommended_wording,
                evidence_status=EvidenceLevel(item.match_type.value) if item.match_type.value in EvidenceLevel._value2member_map_ else EvidenceLevel.MISSING,
            )
            for item in match.matches
            if item.match_type in (MatchType.VERIFIED, MatchType.TRANSFERABLE, MatchType.FAMILIARITY)
            and item.candidate_evidence
        ][:4]

    def build_narrative(
        self,
        profile: CandidateProfile,
        job: JobAnalysis,
        intersections: list[RoleIntersection],
        applicant_notes: str,
    ) -> CandidateNarrative:
        first = intersections[0] if intersections else None
        education = profile.education[0] if profile.education else None
        return CandidateNarrative(
            coming_from=profile.experience[0].role if profile.experience else (education.degree if education else ""),
            already_done=first.candidate_evidence if first else "",
            moving_toward=first.job_need if first else job.position,
            next_step=applicant_notes.strip(),
            company_team_reason=applicant_notes.strip(),
            learning_direction="; ".join(job.preferred_skills[:2]),
        )

    def build_strategy(
        self,
        profile: CandidateProfile,
        job: JobAnalysis,
        need: HiringNeedAnalysis,
        intersections: list[RoleIntersection],
        research: CompanyResearch,
        applicant_notes: str = "",
    ) -> ApplicationStrategy:
        strongest = intersections[0] if intersections else None
        fit = strongest.why_relevant if strongest else ""
        direction = profile.career_direction or applicant_notes.strip()
        return ApplicationStrategy(
            unique_angle=(strongest.possible_letter_use if strongest else "") or need.core_hiring_need,
            technical_fit=fit,
            career_narrative=direction,
            immediate_contribution=strongest.candidate_evidence if strongest else "",
            learning_motivation=applicant_notes.strip() or "; ".join(need.learning_expectations[:2]),
        )

    def analyze_voice(self, writing_samples: list[str]) -> VoiceProfile:
        if not writing_samples:
            return VoiceProfile()
        text = " ".join(writing_samples)
        words = text.split()
        average = len(words) / max(1, len(re.findall(r"[.!?]", text)))
        return VoiceProfile(
            formality="professional" if not any(word in text.casefold() for word in ("lol", "awesome", "super")) else "conversational",
            directness="high" if average < 25 else "moderate",
            technicality="high" if sum(char.isdigit() for char in text) or any(token in text.casefold() for token in ("api", "database", "system", "software")) else "moderate",
            enthusiasm="moderate",
            sentence_length="short" if average < 15 else "medium" if average < 25 else "long",
            vocabulary="technical but accessible",
        )

    def critique(self, text: str, job: JobAnalysis, match: MatchAnalysis) -> RecruiterCritique:
        report = self.quality_report(text, job, match)
        weaknesses = list(report.generic_phrases)
        if report.word_count < 350 or report.word_count > 400:
            weaknesses.append("The letter is outside the required 350–400 word range.")
        return RecruiterCritique(
            strengths=["Uses role-specific evidence." ] if report.candidate_evidence_score >= 70 else [],
            weaknesses=weaknesses,
            generic_phrases=report.generic_phrases,
            missing_requirements=[item.requirement for item in match.matches if item.match_type == MatchType.MISSING],
            revision_instructions=["Replace claims with concrete evidence."] if weaknesses else [],
            score=max(0, 100 - report.genericness_score),
        )

    def validate_facts(self, text: str, profile: CandidateProfile, match: MatchAnalysis) -> FactValidation:
        unsupported = [item.requirement for item in match.matches if item.match_type == MatchType.MISSING and self._positive_claim(text, item.requirement)]
        return FactValidation(passed=not unsupported, unsupported_claims=unsupported)

    @staticmethod
    def _positive_claim(text: str, requirement: str) -> bool:
        normalized = text.casefold()
        target = requirement.casefold().strip()
        index = normalized.find(target)
        if len(target) <= 2 or index < 0:
            return False
        context = normalized[max(0, index - 140):index + len(target) + 100]
        if any(marker in context for marker in (
            "not used", "haven't used", "have not used", "without experience",
            "no direct experience", "not yet", "would like to learn", "want to learn",
            "hope to learn", "develop familiarity", "study", "learning", "build that capability",
        )):
            return False
        target_start = context.find(target)
        prefix = context[:target_start]
        sentence_start = max(prefix.rfind(".") + 1, prefix.rfind("!") + 1, prefix.rfind("?") + 1)
        sentence = context[sentence_start:]
        return any(marker in sentence for marker in (
            "i have", "i used", "i worked with", "i developed", "i implemented",
            "i have developed", "i have implemented", "i have used", "i have worked with",
            "i designed", "i built", "i managed", "i led", "my experience with",
            "my work with", "experience in", "background in", "proficient in",
            "expertise in", "familiar with",
        ))

    def quality_report(self, text: str, job: JobAnalysis, match: MatchAnalysis) -> CoverLetterQualityReport:
        normalized = text.casefold()
        generic = [phrase for phrase in (
            "i am writing to express my interest", "passionate about", "perfect fit",
            "strongly aligns with", "cutting-edge", "valuable opportunity", "results-driven",
            "i am confident that i would be an excellent fit",
        ) if phrase in normalized]
        role_terms = [job.position, job.company, *[item.requirement for item in match.matches if item.match_type == MatchType.VERIFIED]]
        role_hits = sum(bool(term and term.casefold() in normalized) for term in role_terms)
        evidence_hits = sum(bool(item.candidate_evidence and any(token in normalized for token in re.findall(r"[a-z0-9]+", item.candidate_evidence[0].casefold()))) for item in match.matches)
        specific = min(100, 60 + 10 * min(4, role_hits))
        evidence = min(100, 60 + 10 * min(4, evidence_hits))
        return CoverLetterQualityReport(
            specificity_score=specific,
            candidate_evidence_score=evidence,
            company_relevance_score=80 if job.company and job.company.casefold() in normalized else 40,
            role_relevance_score=min(100, 60 + 10 * min(4, role_hits)),
            naturalness_score=max(0, 100 - 15 * len(generic)),
            genericness_score=min(100, 20 * len(generic)),
            word_count=len(re.findall(r"\b[\w+#]+(?:[’'-][\w+#]+)*\b", text, flags=re.UNICODE)),
            generic_phrases=generic,
            requires_review=bool(generic) or specific < 85 or evidence < 85,
        )
