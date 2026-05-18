"""
Recruiting Agents — FastAPI server (Vercel-compatible)

POST /run          → SSE stream: progress events then final JSON result
POST /run/sync     → blocks until done, returns full JSON (simpler, same timeout)
POST /jobs/{id}/interview → analyze interview transcript for a candidate
GET  /health
"""

import sys
import traceback
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import asyncio
import json
import uuid
from typing import Optional, AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from models.candidate import RoleType
from pipeline import run_pipeline, run_interview_analysis, PipelineResult

app = FastAPI(
    title="Livo Health Recruiting Agents",
    description="Agentic AI talent sourcing and recruiting pipeline",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store completed results in-memory (same instance, same request lifecycle on Vercel)
_results: dict[str, PipelineResult] = {}


# ── Request / Response models ──────────────────────────────────────────────────

class RunRequest(BaseModel):
    description: str
    role_type: Optional[str] = None  # "AI Product Manager" | "AI Designer" | etc.
    num_candidates: int = 10
    enrich_top_n: int = 10
    location: Optional[str] = None   # e.g. "Barcelona, Spain"


class InterviewRequest(BaseModel):
    candidate_name: str
    transcript: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _resolve_role(role_type_str: Optional[str]) -> Optional[RoleType]:
    if not role_type_str:
        return None
    role_map = {r.value: r for r in RoleType}
    return role_map.get(role_type_str)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _stream_pipeline(request: RunRequest) -> AsyncGenerator[str, None]:
    """
    Runs the full pipeline in a thread and yields SSE events as it progresses.
    Final event contains the complete results.
    """
    job_id = str(uuid.uuid4())
    progress_queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_event_loop()

    yield _sse("started", {"job_id": job_id, "status": "running"})

    def on_progress(stage: str, msg: str):
        loop.call_soon_threadsafe(
            progress_queue.put_nowait,
            {"stage": stage, "message": msg},
        )

    async def run_in_background():
        role = _resolve_role(request.role_type)
        return await asyncio.to_thread(
            run_pipeline,
            request.description,
            role,
            request.num_candidates,
            request.enrich_top_n,
            on_progress,
            request.location,
        )

    pipeline_task = asyncio.create_task(run_in_background())

    # Drain progress events while pipeline runs
    while not pipeline_task.done():
        try:
            event = await asyncio.wait_for(progress_queue.get(), timeout=0.5)
            yield _sse("progress", event)
        except asyncio.TimeoutError:
            yield _sse("ping", {})  # keep connection alive

    # Drain any remaining progress events
    while not progress_queue.empty():
        yield _sse("progress", progress_queue.get_nowait())

    try:
        result: PipelineResult = pipeline_task.result()
        _results[job_id] = result

        yield _sse("done", {
            "job_id": job_id,
            "stats": result.stats,
            "role": result.job_spec.title,
            "candidates": [c.model_dump() for c in result.outreached],
        })

    except Exception as e:
        yield _sse("error", {"job_id": job_id, "error": str(e)})


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.post("/run")
async def run_streaming(request: RunRequest):
    """
    Start pipeline and stream progress as Server-Sent Events.

    Events: started → progress (many) → ping (keepalive) → done | error

    Final `done` event contains full results: stats + candidates with outreach messages.
    """
    return StreamingResponse(
        _stream_pipeline(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/run/sync")
async def run_sync(request: RunRequest):
    """
    Run the full pipeline synchronously. Blocks until done (up to 5 min).
    Returns the complete result as JSON.
    """
    job_id = str(uuid.uuid4())
    progress_log: list[str] = []

    def on_progress(stage: str, msg: str):
        progress_log.append(f"[{stage.upper()}] {msg}")

    role = _resolve_role(request.role_type)

    try:
        result: PipelineResult = await asyncio.to_thread(
            run_pipeline,
            request.description,
            role,
            request.num_candidates,
            request.enrich_top_n,
            on_progress,
            request.location,
        )
        _results[job_id] = result

        return {
            "job_id": job_id,
            "status": "done",
            "role": result.job_spec.title,
            "stats": result.stats,
            "progress_log": progress_log,
            "candidates": [c.model_dump() for c in result.outreached],
            "all_scored": [c.model_dump() for c in result.scored],
        }
    except Exception as e:
        tb = traceback.format_exc()
        return {"job_id": job_id, "status": "failed", "error": str(e), "traceback": tb, "progress_log": progress_log}


@app.post("/jobs/{job_id}/interview")
async def analyze_interview(job_id: str, request: InterviewRequest):
    """Analyze an interview transcript for a candidate from a completed pipeline run."""
    result = _results.get(job_id)
    if not result:
        raise HTTPException(status_code=404, detail="Job not found — results are in-memory and may have expired")

    insights = run_interview_analysis(result, request.candidate_name, request.transcript)
    if not insights:
        raise HTTPException(status_code=404, detail=f"Candidate '{request.candidate_name}' not found")

    return insights.model_dump()


@app.get("/health")
async def health():
    return {"status": "ok", "cached_results": len(_results)}
