from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field


class EvidenceLevel(str, Enum):
    VERIFIED = "VERIFIED"
    TRANSFERABLE = "TRANSFERABLE"
    FAMILIARITY = "FAMILIARITY"
    MISSING = "MISSING"


class MatchType(str, Enum):
    VERIFIED = "VERIFIED"
    TRANSFERABLE = "TRANSFERABLE"
    FAMILIARITY = "FAMILIARITY"
    MISSING = "MISSING"
    CONFLICT = "CONFLICT"


class Personal(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    website: str = ""
    github: str = ""
    languages: list[str] = Field(default_factory=list)


class Education(BaseModel):
    institution: str = ""
    degree: str = ""
    field: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    details: list[str] = Field(default_factory=list)


class Experience(BaseModel):
    company: str = ""
    role: str = ""
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    summary: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    evidence_level: EvidenceLevel = EvidenceLevel.VERIFIED
    notes: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class Project(BaseModel):
    name: str = ""
    description: str = ""
    domain: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    relevance_tags: list[str] = Field(default_factory=list)


class Skill(BaseModel):
    name: str
    status: EvidenceLevel = EvidenceLevel.VERIFIED
    evidence: list[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    personal: Personal = Field(default_factory=Personal)
    education: list[Education] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    preferences: dict[str, str] = Field(default_factory=dict)
    interests: list[str] = Field(default_factory=list)
    career_direction: str = ""
    writing_samples: list[str] = Field(default_factory=list)


class JobAnalysis(BaseModel):
    analysis_method: str = "local"
    analysis_warning: str = ""
    job_language: Literal["English", "French"] = "English"
    company: str = ""
    department: str = ""
    position: str = ""
    location: str = ""
    employment_type: str = ""
    start_date: str = ""
    duration: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    technical_skills: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    domain_keywords: list[str] = Field(default_factory=list)
    education_requirements: list[str] = Field(default_factory=list)
    language_requirements: list[str] = Field(default_factory=list)
    tools_and_technologies: list[str] = Field(default_factory=list)
    implicit_requirements: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    likely_daily_activities: list[str] = Field(default_factory=list)


class RequirementMatch(BaseModel):
    requirement: str
    importance: str = "MEDIUM"
    match_type: MatchType
    candidate_evidence: list[str] = Field(default_factory=list)
    recommended_wording: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class MatchAnalysis(BaseModel):
    analysis_method: str = "local"
    analysis_warning: str = ""
    matches: list[RequirementMatch] = Field(default_factory=list)
    score: int = 0
    summary: str = ""
    learning_recommendations: list[dict[str, str]] = Field(default_factory=list)


class JobUnderstanding(BaseModel):
    concrete_activities: list[str] = Field(default_factory=list)
    technical_needs: list[str] = Field(default_factory=list)
    domain_needs: list[str] = Field(default_factory=list)
    learning_expectations: list[str] = Field(default_factory=list)
    implicit_needs: list[str] = Field(default_factory=list)
    source_requirements: dict[str, list[str]] = Field(default_factory=dict)


class HiringNeedAnalysis(BaseModel):
    core_hiring_need: str = ""
    technical_needs: list[str] = Field(default_factory=list)
    domain_needs: list[str] = Field(default_factory=list)
    working_style_needs: list[str] = Field(default_factory=list)
    learning_expectations: list[str] = Field(default_factory=list)
    implicit_needs: list[str] = Field(default_factory=list)


class CompanyResearch(BaseModel):
    company_context: list[str] = Field(default_factory=list)
    team_context: list[str] = Field(default_factory=list)
    technical_context: list[str] = Field(default_factory=list)
    relevant_programmes: list[str] = Field(default_factory=list)
    candidate_relevant_points: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    verified: bool = False


class EvidenceRecord(BaseModel):
    claim: str
    evidence: str
    source: str
    evidence_level: EvidenceLevel
    recency: str = ""
    measurable_result: str = ""
    relevance_tags: list[str] = Field(default_factory=list)


class RoleIntersection(BaseModel):
    job_need: str
    candidate_evidence: str
    strength: str = "MEDIUM"
    recommended_use: str = ""
    why_relevant: str = ""
    possible_letter_use: str = ""
    evidence_status: EvidenceLevel = EvidenceLevel.VERIFIED


class CandidateNarrative(BaseModel):
    coming_from: str = ""
    already_done: str = ""
    moving_toward: str = ""
    next_step: str = ""
    company_team_reason: str = ""
    learning_direction: str = ""


class ApplicationStrategy(BaseModel):
    unique_angle: str = ""
    technical_fit: str = ""
    career_narrative: str = ""
    immediate_contribution: str = ""
    learning_motivation: str = ""


class VoiceProfile(BaseModel):
    formality: str = "professional"
    directness: str = "high"
    technicality: str = "high"
    enthusiasm: str = "moderate"
    sentence_length: str = "medium"
    vocabulary: str = "technical but accessible"


class RecruiterCritique(BaseModel):
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    generic_phrases: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    revision_instructions: list[str] = Field(default_factory=list)
    score: int = Field(default=0, ge=0, le=100)


class FactValidation(BaseModel):
    passed: bool = False
    unsupported_claims: list[str] = Field(default_factory=list)
    overstated_evidence: list[str] = Field(default_factory=list)
    missing_sources: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class CoverLetterQualityReport(BaseModel):
    specificity_score: int = 0
    candidate_evidence_score: int = 0
    company_relevance_score: int = 0
    role_relevance_score: int = 0
    naturalness_score: int = 0
    genericness_score: int = 0
    generic_phrases: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    requires_review: bool = True
    word_count: int = 0
    fact_validation: FactValidation = Field(default_factory=FactValidation)
