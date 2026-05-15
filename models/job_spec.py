from pydantic import BaseModel, Field
from typing import Optional
from models.candidate import RoleType


class JobSpec(BaseModel):
    role_type: RoleType
    title: str
    company: str = "Livo Health"
    location: Optional[str] = None
    remote_ok: bool = True
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    experience_years_min: int = 3
    experience_years_max: Optional[int] = None
    key_responsibilities: list[str] = Field(default_factory=list)
    ideal_background: Optional[str] = None
    red_flags: list[str] = Field(default_factory=list)
    sourcing_keywords: list[str] = Field(default_factory=list)
    preferred_platforms: list[str] = Field(default_factory=list)

    @classmethod
    def for_ai_pm(cls) -> "JobSpec":
        return cls(
            role_type=RoleType.AI_PM,
            title="AI Product Manager",
            required_skills=["product strategy", "AI/ML", "roadmapping", "stakeholder management"],
            nice_to_have_skills=["LLM APIs", "prompt engineering", "data analytics", "user research"],
            experience_years_min=4,
            key_responsibilities=[
                "Define AI product vision and roadmap",
                "Collaborate with ML engineers and designers",
                "Drive adoption of AI features",
                "Translate business problems into AI opportunities",
            ],
            sourcing_keywords=["AI product manager", "ML product", "LLM product", "generative AI PM"],
            preferred_platforms=["LinkedIn", "Twitter/X", "Product Hunt"],
        )

    @classmethod
    def for_ai_designer(cls) -> "JobSpec":
        return cls(
            role_type=RoleType.AI_DESIGNER,
            title="AI/UX Designer",
            required_skills=["UX design", "AI interaction design", "prototyping", "user research"],
            nice_to_have_skills=["Figma", "LLM interfaces", "conversation design", "design systems"],
            experience_years_min=3,
            key_responsibilities=[
                "Design AI-powered user experiences",
                "Create intuitive interfaces for complex AI features",
                "Conduct user research on AI product interactions",
                "Build and maintain design systems",
            ],
            sourcing_keywords=["AI UX designer", "LLM interface designer", "conversational UI", "AI product designer"],
            preferred_platforms=["LinkedIn", "Dribbble", "Behance", "Twitter/X"],
        )

    @classmethod
    def for_ai_engineer(cls) -> "JobSpec":
        return cls(
            role_type=RoleType.AI_ENGINEER,
            title="AI/ML Engineer",
            required_skills=["Python", "machine learning", "LLMs", "API integration"],
            nice_to_have_skills=["PyTorch", "HuggingFace", "RAG", "fine-tuning", "MLOps"],
            experience_years_min=3,
            key_responsibilities=[
                "Build and deploy AI/ML models",
                "Integrate LLMs into production systems",
                "Design scalable AI infrastructure",
                "Collaborate with data scientists on model development",
            ],
            sourcing_keywords=["AI engineer", "ML engineer", "LLM engineer", "GenAI engineer"],
            preferred_platforms=["GitHub", "HuggingFace", "LinkedIn", "ArXiv"],
        )

    @classmethod
    def for_data_scientist(cls) -> "JobSpec":
        return cls(
            role_type=RoleType.DATA_SCIENTIST,
            title="Data Scientist (AI Focus)",
            required_skills=["Python", "statistics", "machine learning", "data analysis"],
            nice_to_have_skills=["NLP", "deep learning", "Kaggle competitions", "SQL", "spark"],
            experience_years_min=2,
            key_responsibilities=[
                "Develop predictive models and analytics",
                "Extract insights from complex datasets",
                "Build ML pipelines for production",
                "Communicate findings to stakeholders",
            ],
            sourcing_keywords=["data scientist", "ML scientist", "AI researcher", "applied scientist"],
            preferred_platforms=["Kaggle", "LinkedIn", "GitHub", "ArXiv"],
        )
