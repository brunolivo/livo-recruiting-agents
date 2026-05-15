from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class RoleType(str, Enum):
    AI_PM = "AI Product Manager"
    AI_DESIGNER = "AI Designer"
    AI_ENGINEER = "AI Engineer"
    DATA_SCIENTIST = "Data Scientist"


class CandidateSource(str, Enum):
    LINKEDIN = "LinkedIn"
    GITHUB = "GitHub"
    HUGGINGFACE = "HuggingFace"
    KAGGLE = "Kaggle"
    TWITTER = "Twitter/X"
    DRIBBBLE = "Dribbble"
    ARXIV = "ArXiv"
    COMMUNITY = "Community"


class Candidate(BaseModel):
    name: str
    role_type: RoleType
    source: CandidateSource
    profile_url: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    skills: list[str] = Field(default_factory=list)
    experience_years: Optional[int] = None
    notable_work: Optional[str] = None
    open_source_contributions: Optional[str] = None
    publications: Optional[str] = None
    portfolio_url: Optional[str] = None
    raw_profile_data: Optional[str] = None


class EnrichedCandidate(Candidate):
    enriched_summary: Optional[str] = None
    ai_expertise_depth: Optional[str] = None
    recent_activity: Optional[str] = None
    community_presence: Optional[str] = None


class ScoredCandidate(EnrichedCandidate):
    fit_score: float = 0.0
    technical_score: float = 0.0
    culture_score: float = 0.0
    scoring_rationale: Optional[str] = None
    recommended: bool = False


class OutreachedCandidate(ScoredCandidate):
    outreach_subject: Optional[str] = None
    outreach_message: Optional[str] = None
    outreach_channel: Optional[str] = None


class InterviewInsights(BaseModel):
    candidate_name: str
    key_strengths: list[str] = Field(default_factory=list)
    areas_of_concern: list[str] = Field(default_factory=list)
    technical_assessment: Optional[str] = None
    cultural_fit_assessment: Optional[str] = None
    recommendation: Optional[str] = None
    next_steps: list[str] = Field(default_factory=list)
    summary: Optional[str] = None
