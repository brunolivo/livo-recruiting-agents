"""
Recruiting Pipeline Orchestrator

Connects all agents in sequence:
  Job Spec → Sourcing → Enrichment → Scoring → Outreach → (Interview)

Each stage feeds directly into the next. Results are accumulated into a
PipelineResult object that can be saved, displayed, or passed to downstream tools.
"""

from dataclasses import dataclass, field
from models.job_spec import JobSpec
from models.candidate import (
    Candidate,
    EnrichedCandidate,
    ScoredCandidate,
    OutreachedCandidate,
    InterviewInsights,
    RoleType,
)
from agents.job_spec_agent import parse_job_requirements
from agents.sourcing_agent import source_candidates
from agents.enrichment_agent import enrich_candidates_batch
from agents.scoring_agent import score_and_rank_candidates
from agents.outreach_agent import generate_outreach_batch
from agents.interview_agent import analyze_interview


@dataclass
class PipelineResult:
    job_spec: JobSpec
    sourced: list[Candidate] = field(default_factory=list)
    enriched: list[EnrichedCandidate] = field(default_factory=list)
    scored: list[ScoredCandidate] = field(default_factory=list)
    outreached: list[OutreachedCandidate] = field(default_factory=list)
    interview_insights: list[InterviewInsights] = field(default_factory=list)

    @property
    def top_candidates(self) -> list[ScoredCandidate]:
        return [c for c in self.scored if c.recommended]

    @property
    def stats(self) -> dict:
        return {
            "sourced": len(self.sourced),
            "enriched": len(self.enriched),
            "scored": len(self.scored),
            "recommended": len(self.top_candidates),
            "outreached": len(self.outreached),
        }


def run_pipeline(
    raw_description: str,
    role_type: RoleType | None = None,
    num_candidates: int = 10,
    enrich_top_n: int = 10,
    on_progress=None,
) -> PipelineResult:
    """
    Run the full recruiting pipeline end to end.

    Args:
        raw_description: Free-form job description or requirements
        role_type: Optional role type hint (auto-detected if None)
        num_candidates: How many candidates to source
        enrich_top_n: How many candidates to enrich (enrichment is expensive)
        on_progress: Optional callback(stage_name, message) for progress updates
    """

    def progress(stage: str, msg: str):
        if on_progress:
            on_progress(stage, msg)

    # Stage 1: Parse job requirements
    progress("job_spec", f"Parsing job requirements for: {raw_description[:60]}...")
    job_spec = parse_job_requirements(raw_description, role_type)
    progress("job_spec", f"Job spec created: {job_spec.title} at {job_spec.company}")

    result = PipelineResult(job_spec=job_spec)

    # Stage 2: Source candidates
    progress("sourcing", f"Sourcing {num_candidates} {job_spec.role_type.value} candidates...")
    result.sourced = source_candidates(job_spec, num_candidates=num_candidates)
    progress("sourcing", f"Found {len(result.sourced)} candidates across platforms")

    if not result.sourced:
        progress("sourcing", "No candidates found — pipeline stopping early")
        return result

    # Stage 3: Enrich top candidates
    to_enrich = result.sourced[:enrich_top_n]
    progress("enrichment", f"Enriching {len(to_enrich)} candidate profiles...")
    result.enriched = enrich_candidates_batch(to_enrich)
    progress("enrichment", f"Enrichment complete for {len(result.enriched)} candidates")

    # Stage 4: Score and rank
    progress("scoring", "Scoring candidates against job requirements...")
    result.scored = score_and_rank_candidates(result.enriched, job_spec)
    recommended_count = sum(1 for c in result.scored if c.recommended)
    progress("scoring", f"Scored {len(result.scored)} candidates — {recommended_count} recommended")

    # Stage 5: Generate outreach for recommended candidates
    if recommended_count > 0:
        progress("outreach", f"Crafting personalized outreach for {recommended_count} candidates...")
        result.outreached = generate_outreach_batch(result.scored, job_spec)
        progress("outreach", f"Outreach ready for {len(result.outreached)} candidates")
    else:
        progress("outreach", "No recommended candidates — skipping outreach")

    return result


def run_interview_analysis(
    result: PipelineResult,
    candidate_name: str,
    transcript: str,
) -> InterviewInsights | None:
    """
    Analyze an interview transcript for a specific candidate in the pipeline.
    Appends insights to the PipelineResult and returns them.
    """
    candidate = next(
        (c for c in result.scored if c.name.lower() == candidate_name.lower()),
        None,
    )
    if not candidate:
        return None

    insights = analyze_interview(candidate, transcript, result.job_spec)
    result.interview_insights.append(insights)
    return insights
