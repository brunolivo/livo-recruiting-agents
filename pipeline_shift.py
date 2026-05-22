"""
Shift Staffing Pipeline — Livo Healthcare Critical Shifts

Flow:
  1. Parse shift description → structured Shift object
  2. Source professionals from Metabase repeaters DB
  3. Score and rank by facility/unit history and recency
  4. Generate personalised Spanish WhatsApp messages
  5. Return ShiftPipelineResult

Usage:
  result = run_shift_pipeline(
      shift_description="Matrona dia 22 a las 20h20 a las 08am turno de 12 horas",
      facility_name="Hospital General de Catalunya",
      unit="Maternidad",
  )
"""

from models.shift import Shift, ShiftPipelineResult, ContactedProfessional
from agents.shift_sourcing_agent import parse_shift, source_professionals
from agents.shift_scoring_agent import score_professionals
from agents.shift_outreach_agent import generate_outreach_batch


def run_shift_pipeline(
    shift_description: str,
    facility_name: str,
    unit: str = "",
    num_professionals: int = 15,
    on_progress=None,
) -> ShiftPipelineResult:
    """
    Run the full shift staffing pipeline end-to-end.

    Args:
        shift_description: Free-text shift description in Spanish
                           e.g. "Matrona dia 22 a las 20h20 a las 08am turno de 12 horas"
        facility_name:     Hospital/clinic name as it appears in Metabase
        unit:              Optional unit/ward (e.g. "Maternidad", "UCI")
        num_professionals: How many professionals to surface
        on_progress:       Optional callback(stage, message) for SSE progress
    """

    def progress(stage: str, msg: str):
        if on_progress:
            on_progress(stage, msg)

    # ── Stage 1: Parse shift ─────────────────────────────────────────────────
    progress("parse", f"Analizando turno: {shift_description[:60]}…")
    shift = parse_shift(shift_description, facility_name, unit)
    progress("parse", f"Turno identificado: {shift.display_label}")

    # ── Stage 2: Source professionals ────────────────────────────────────────
    progress("sourcing", f"Buscando {shift.role.value}s en {facility_name}…")
    professionals = source_professionals(shift, count=num_professionals * 2)
    progress("sourcing", f"Encontrados {len(professionals)} profesionales en la base de datos")

    if not professionals:
        progress("sourcing", "Sin datos de Metabase — configura METABASE_USERNAME/PASSWORD en .env")
        return ShiftPipelineResult(
            shift=shift,
            professionals=[],
            stats={"sourced": 0, "recommended": 0, "contacted": 0},
        )

    # ── Stage 3: Score and rank ──────────────────────────────────────────────
    progress("scoring", f"Puntuando {len(professionals)} perfiles por historial en el centro…")
    scored = score_professionals(professionals, shift)
    recommended = sum(1 for p in scored if p.recommended)
    progress("scoring", f"{recommended} profesionales recomendados de {len(scored)}")

    # ── Stage 4: Generate outreach messages ──────────────────────────────────
    top = scored[:num_professionals]
    progress("outreach", f"Redactando mensajes WhatsApp en español para {recommended} profesionales…")
    contacted = generate_outreach_batch(top, shift)
    progress("outreach", f"Mensajes listos para {sum(1 for p in contacted if p.message_body)} profesionales")

    stats = {
        "sourced":     len(professionals),
        "scored":      len(scored),
        "recommended": recommended,
        "contacted":   sum(1 for p in contacted if p.message_body),
    }

    return ShiftPipelineResult(
        shift=shift,
        professionals=contacted,
        stats=stats,
    )
