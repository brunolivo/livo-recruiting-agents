"""
Shift Sourcing Agent — finds available healthcare professionals for a critical shift.

Sources:
  1. Metabase repeaters DB (primary) — professionals who have worked at the facility before
  2. LLM fallback — if Metabase is not configured, uses web search as a stub

The agent parses the shift description, queries the repeaters database filtered by
facility + role (+ unit if provided), and returns structured HealthcareProfessional objects.
"""

import json
import re
from models.shift import (
    Shift, HealthcareProfessional, HealthcareRole,
    KEYWORD_TO_ROLE, ROLE_TO_METABASE,
)
from agents.base_agent import run_agent
from tools import metabase_api


PARSE_SYSTEM_PROMPT = """Eres un asistente experto en turnos sanitarios.
Extrae los datos del turno del texto libre proporcionado."""


def parse_shift(description: str, facility_name: str, unit: str = "") -> Shift:
    """
    Parse a free-text shift description into a structured Shift object.
    Example: "Matrona dia 22 a las 20h20 a las 08am turno de 12 horas"
    """
    # Try fast regex parse first
    shift = _fast_parse(description, facility_name, unit)
    if shift:
        return shift

    # Fall back to LLM parse
    return _llm_parse(description, facility_name, unit)


def _fast_parse(description: str, facility_name: str, unit: str) -> Shift | None:
    """Quick regex-based parser for common Spanish shift description formats."""
    text = description.lower().strip()

    # Detect role
    role: HealthcareRole | None = None
    for keyword, r in KEYWORD_TO_ROLE.items():
        if keyword in text:
            role = r
            break
    if not role:
        return None

    # Detect duration
    duration = 12.0
    dur_match = re.search(r"(\d+)\s*h(?:oras?)?", text)
    if dur_match:
        duration = float(dur_match.group(1))

    # Detect day number
    day_match = re.search(r"d[ií]a\s+(\d{1,2})", text)
    day = day_match.group(1) if day_match else "?"

    # Detect times — accepts "20h20", "20:20", "08am", "08h", "08:00"
    times = re.findall(r"(\d{1,2})(?:h|:)(\d{2})?(?:am|pm)?", text)
    # Filter out the duration match
    time_strs = []
    for h, m in times:
        hh = int(h)
        mm = int(m) if m else 0
        time_str = f"{hh:02d}:{mm:02d}"
        if time_str not in time_strs:
            time_strs.append(time_str)

    # Remove duration from time list (e.g. "12" from "12 horas")
    if dur_match:
        dur_str = f"{int(duration):02d}:00"
        time_strs = [t for t in time_strs if t != dur_str]

    start_time = time_strs[0] if len(time_strs) >= 1 else "00:00"
    end_time   = time_strs[1] if len(time_strs) >= 2 else "12:00"

    # Build a readable date string
    month_names = {
        1: "enero", 2: "febrero", 3: "marzo", 4: "abril",
        5: "mayo", 6: "junio", 7: "julio", 8: "agosto",
        9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
    }
    from datetime import date
    today = date.today()
    date_str = f"{day} de {month_names.get(today.month, '')}"

    return Shift(
        role=role,
        facility_name=facility_name,
        unit=unit or None,
        date_str=date_str,
        start_time=start_time,
        end_time=end_time,
        duration_hours=duration,
        raw_description=description,
    )


def _llm_parse(description: str, facility_name: str, unit: str) -> Shift:
    """Use LLM to parse an ambiguous shift description."""
    roles_list = ", ".join(r.value for r in HealthcareRole)
    prompt = f"""Extrae los datos de este turno sanitario y devuelve JSON:

Descripción: "{description}"
Centro: "{facility_name}"
Unidad: "{unit}"

Roles disponibles: {roles_list}

Devuelve SOLO este JSON:
{{
  "role": "Matrona",
  "date_str": "22 de mayo",
  "start_time": "20:20",
  "end_time": "08:00",
  "duration_hours": 12
}}"""

    result = run_agent(
        system_prompt=PARSE_SYSTEM_PROMPT,
        user_message=prompt,
        agent_name="Shift Parser",
        use_web_search=False,
    )

    try:
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        start, end = clean.find("{"), clean.rfind("}") + 1
        data = json.loads(clean[start:end])

        role_map = {r.value: r for r in HealthcareRole}
        role = role_map.get(data.get("role", ""), HealthcareRole.ENFERMERA)

        return Shift(
            role=role,
            facility_name=facility_name,
            unit=unit or None,
            date_str=data.get("date_str", ""),
            start_time=data.get("start_time", "00:00"),
            end_time=data.get("end_time", "12:00"),
            duration_hours=float(data.get("duration_hours", 12)),
            raw_description=description,
        )
    except Exception:
        return Shift(
            role=HealthcareRole.ENFERMERA,
            facility_name=facility_name,
            unit=unit or None,
            date_str="",
            start_time="00:00",
            end_time="12:00",
            duration_hours=12.0,
            raw_description=description,
        )


# ── Sourcing ──────────────────────────────────────────────────────────────────

def source_professionals(
    shift: Shift,
    count: int = 20,
) -> list[HealthcareProfessional]:
    """
    Source healthcare professionals for the given shift.
    Primary: Metabase repeaters DB.
    Fallback: returns empty list (no Metabase credentials).
    """
    raw = metabase_api.query_repeaters(
        facility_name=shift.facility_name,
        professional_field=shift.metabase_field,
        unit=shift.unit or "",
    )

    if raw:
        return _map_professionals(raw, shift, count)

    # No Metabase data — return empty (scoring/outreach still run on whatever we have)
    return []


def _map_professionals(
    raw: list[dict],
    shift: Shift,
    count: int,
) -> list[HealthcareProfessional]:
    """Map raw Metabase rows to HealthcareProfessional objects."""
    professionals: list[HealthcareProfessional] = []

    for row in raw[:count]:
        name = (row.get("name") or "").strip()
        if not name:
            continue

        professionals.append(HealthcareProfessional(
            name=name,
            role=shift.role,
            source="Metabase",
            professional_id=str(row.get("professional_id") or ""),
            phone=row.get("phone") or None,
            email=row.get("email") or None,
            facility_name=row.get("facility_name") or shift.facility_name,
            unit=row.get("unit") or shift.unit or None,
            shifts_at_facility=int(row.get("shifts_at_facility") or 0),
            shifts_in_unit=int(row.get("shifts_in_unit") or 0),
            total_shifts=int(row.get("total_shifts") or row.get("shifts_at_facility") or 0),
            last_shift_date=str(row.get("last_shift_date") or ""),
            location=row.get("location") or None,
        ))

    return professionals
