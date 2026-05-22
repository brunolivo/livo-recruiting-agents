"""
Shift Scoring Agent — ranks healthcare professionals for a specific shift.

Scoring signals:
  - shifts_at_facility (0-40 pts): primary signal — they know the center
  - shifts_in_unit     (0-30 pts): bonus if they've worked this specific unit
  - total_shifts       (0-20 pts): overall platform experience
  - recency            (0-10 pts): how recently they last worked

Final fit_score is normalised to 0-10.
recommended = True if fit_score >= 6.0
"""

from datetime import date, datetime
from models.shift import Shift, HealthcareProfessional, ScoredProfessional


def score_professionals(
    professionals: list[HealthcareProfessional],
    shift: Shift,
) -> list[ScoredProfessional]:
    """
    Score and rank all professionals for this shift.
    Returns list sorted by fit_score descending.
    """
    if not professionals:
        return []

    scored = [_score_one(p, shift) for p in professionals]
    return sorted(scored, key=lambda p: p.fit_score, reverse=True)


def _score_one(p: HealthcareProfessional, shift: Shift) -> ScoredProfessional:
    # ── Facility familiarity (0–40) ──────────────────────────────────────────
    fac_pts = min(p.shifts_at_facility, 20) * 2.0   # caps at 40 pts for 20+ shifts

    # ── Unit familiarity (0–30) ───────────────────────────────────────────────
    unit_pts = min(p.shifts_in_unit, 15) * 2.0 if p.shifts_in_unit else 0.0
    # If unit info is not broken out, use 40% of facility shifts as proxy
    if unit_pts == 0 and p.shifts_at_facility > 0 and shift.unit:
        unit_pts = min(p.shifts_at_facility * 0.4 * 2.0, 12.0)

    # ── Overall experience (0–20) ─────────────────────────────────────────────
    total = p.total_shifts or p.shifts_at_facility
    exp_pts = min(total, 50) * 0.4                   # caps at 20 pts for 50+ shifts

    # ── Recency (0–10) ───────────────────────────────────────────────────────
    recency_pts = _recency_score(p.last_shift_date)

    raw = fac_pts + unit_pts + exp_pts + recency_pts   # 0–100
    fit_score = round(min(raw / 10.0, 10.0), 2)        # normalise to 0-10

    # Sub-scores for display
    experience_score  = round(min((fac_pts + unit_pts) / 7.0, 10.0), 2)
    availability_score = round(min((recency_pts + exp_pts) / 3.0, 10.0), 2)

    recommended = fit_score >= 6.0

    rationale = _build_rationale(p, shift, fac_pts, unit_pts, exp_pts, recency_pts)

    return ScoredProfessional(
        **p.model_dump(),
        experience_score=experience_score,
        availability_score=availability_score,
        fit_score=fit_score,
        scoring_rationale=rationale,
        recommended=recommended,
    )


def _recency_score(last_shift_date: str | None) -> float:
    """Return 0–10 recency score. Recent shifts → higher score."""
    if not last_shift_date:
        return 3.0  # unknown — give neutral score
    try:
        # Parse common date formats
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                last = datetime.strptime(last_shift_date, fmt).date()
                break
            except ValueError:
                continue
        else:
            return 3.0

        days_ago = (date.today() - last).days
        if days_ago <= 30:    return 10.0
        if days_ago <= 90:    return 8.0
        if days_ago <= 180:   return 6.0
        if days_ago <= 365:   return 4.0
        if days_ago <= 730:   return 2.0
        return 1.0
    except Exception:
        return 3.0


def _build_rationale(
    p: HealthcareProfessional,
    shift: Shift,
    fac_pts: float,
    unit_pts: float,
    exp_pts: float,
    recency_pts: float,
) -> str:
    parts: list[str] = []

    if p.shifts_at_facility > 0:
        parts.append(f"{p.shifts_at_facility} turno(s) en {shift.facility_name}")
    if p.shifts_in_unit > 0 and shift.unit:
        parts.append(f"{p.shifts_in_unit} en unidad {shift.unit}")
    if p.total_shifts > p.shifts_at_facility:
        parts.append(f"{p.total_shifts} turnos totales en Livo")
    if p.last_shift_date:
        parts.append(f"último turno: {p.last_shift_date}")

    return " · ".join(parts) if parts else "Sin historial previo registrado"
