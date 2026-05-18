"""
Job Spec Agent — Parses requirements and creates a structured ideal candidate profile.
Equivalent to the intake/configuration step in Juicebox and Talent River.
"""

import json
from models.job_spec import JobSpec
from models.candidate import RoleType
from agents.base_agent import run_agent

SYSTEM_PROMPT = """You are an expert technical recruiter and talent strategist specializing in AI roles.
Your job is to deeply analyze hiring requirements and create highly specific candidate profiles.

You focus on four AI role types:
- AI Product Managers: bridge business strategy and AI implementation
- AI Designers: craft human-AI interaction experiences
- AI Engineers: build and deploy production AI systems
- Data Scientists: extract insights and build ML models

When given a role or free-form description, you:
1. Identify the exact role type and seniority
2. Extract must-have vs. nice-to-have requirements
3. Identify the best sourcing platforms for this profile
4. Define specific keywords to find this candidate
5. Describe red flags to avoid

Be specific and actionable. Think like a top-tier executive recruiter."""


def parse_job_requirements(raw_description: str, role_type: RoleType | None = None, location: str | None = None) -> JobSpec:
    """
    Takes a free-form job description and returns a structured JobSpec.
    """
    if role_type == RoleType.AI_PM:
        base = JobSpec.for_ai_pm()
    elif role_type == RoleType.AI_DESIGNER:
        base = JobSpec.for_ai_designer()
    elif role_type == RoleType.AI_ENGINEER:
        base = JobSpec.for_ai_engineer()
    elif role_type == RoleType.DATA_SCIENTIST:
        base = JobSpec.for_data_scientist()
    else:
        base = None

    location_hint = f"\nLocation requirement: {location}" if location else ""
    prompt = f"""Analyze this hiring requirement and return a structured candidate profile as JSON.

Raw description: {raw_description}{location_hint}

{"Base template to refine: " + base.model_dump_json(indent=2) if base else ""}

Return a JSON object with these fields:
{{
  "role_type": "AI Product Manager|AI Designer|AI Engineer|Data Scientist",
  "title": "specific job title",
  "company": "Livo Health",
  "remote_ok": true/false,
  "required_skills": ["skill1", "skill2"],
  "nice_to_have_skills": ["skill1", "skill2"],
  "experience_years_min": number,
  "key_responsibilities": ["resp1", "resp2"],
  "ideal_background": "description of ideal candidate background",
  "red_flags": ["red flag 1", "red flag 2"],
  "sourcing_keywords": ["keyword1", "keyword2"],
  "preferred_platforms": ["LinkedIn", "GitHub", etc]
}}

Return ONLY the JSON, no other text."""

    result = run_agent(
        system_prompt=SYSTEM_PROMPT,
        user_message=prompt,
        agent_name="Job Spec Agent",
        use_web_search=False,
    )

    # Parse the JSON response
    try:
        # Strip markdown code blocks if present
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        data = json.loads(clean.strip())
        return JobSpec(**data)
    except Exception:
        # Fallback to base template or defaults
        spec = base or JobSpec(role_type=role_type or RoleType.AI_ENGINEER, title="AI Role")
        if location and not spec.location:
            spec.location = location
        return spec
