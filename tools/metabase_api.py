"""
Metabase API client — queries the Livo repeaters database.

Question 12652: "Repeaters by facility and units fields"
URL: https://livo.metabaseapp.com/question/12652

Template tag parameters:
  livo_unit          → unit/ward filter (empty = all units)
  professional_field → role filter (MIDWIVES, NURSES, DOCTORS, …)
  facility_name      → facility filter

Auth options (set in .env):
  METABASE_USERNAME + METABASE_PASSWORD → session-based auth (always works)
  METABASE_API_KEY                      → direct API key (Metabase 47+, faster)

Set METABASE_URL if your instance is not at https://livo.metabaseapp.com.
"""

import os
import httpx
from typing import Optional

METABASE_URL      = os.getenv("METABASE_URL", "https://livo.metabaseapp.com")
METABASE_USER     = os.getenv("METABASE_USERNAME", "")
METABASE_PASS     = os.getenv("METABASE_PASSWORD", "")
METABASE_API_KEY  = os.getenv("METABASE_API_KEY", "")

REPEATERS_CARD_ID = 12652

# Cache the session token for the lifetime of the process
_session_token: Optional[str] = None


# ── Auth ─────────────────────────────────────────────────────────────────────

def _get_headers() -> dict:
    """Return auth headers. API key takes priority over session token."""
    if METABASE_API_KEY:
        return {"X-API-Key": METABASE_API_KEY, "Content-Type": "application/json"}

    token = _get_session_token()
    if token:
        return {"X-Metabase-Session": token, "Content-Type": "application/json"}

    return {"Content-Type": "application/json"}


def _get_session_token() -> Optional[str]:
    global _session_token
    if _session_token:
        return _session_token
    if not METABASE_USER or not METABASE_PASS:
        return None
    try:
        r = httpx.post(
            f"{METABASE_URL}/api/session",
            json={"username": METABASE_USER, "password": METABASE_PASS},
            timeout=15,
        )
        if r.status_code == 200:
            _session_token = r.json().get("id")
            return _session_token
    except Exception:
        pass
    return None


# ── Public entry point ────────────────────────────────────────────────────────

def query_repeaters(
    facility_name: str,
    professional_field: str,
    unit: str = "",
) -> list[dict]:
    """
    Query the repeaters question (card 12652) filtered by facility, role, and unit.
    Returns a list of professional profile dicts with normalised keys.

    Falls back to an empty list if Metabase credentials are not configured.
    """
    if not METABASE_API_KEY and not (METABASE_USER and METABASE_PASS):
        # Return empty — pipeline will fall back to LLM-based sourcing
        return []

    raw_rows = _run_card(
        card_id=REPEATERS_CARD_ID,
        facility_name=facility_name,
        professional_field=professional_field,
        unit=unit,
    )
    return raw_rows


def _run_card(
    card_id: int,
    facility_name: str,
    professional_field: str,
    unit: str,
) -> list[dict]:
    """POST /api/card/{id}/query with template-tag parameters."""
    parameters = [
        {
            "type":   "category",
            "target": ["variable", ["template-tag", "professional_field"]],
            "value":  professional_field or None,
        },
        {
            "type":   "category",
            "target": ["variable", ["template-tag", "facility_name"]],
            "value":  facility_name or None,
        },
        {
            "type":   "category",
            "target": ["variable", ["template-tag", "livo_unit"]],
            "value":  unit or None,
        },
    ]

    try:
        r = httpx.post(
            f"{METABASE_URL}/api/card/{card_id}/query",
            headers=_get_headers(),
            json={"ignore_cache": False, "parameters": parameters},
            timeout=30,
        )
        if r.status_code != 202 and r.status_code != 200:
            return []
        return _parse_response(r.json())
    except Exception:
        return []


def _parse_response(response: dict) -> list[dict]:
    """
    Convert Metabase query response into a list of normalised dicts.

    Metabase returns:
      data.cols  → list of {"name": "column_name", ...}
      data.rows  → list of row arrays (values in same order as cols)
    """
    try:
        data = response.get("data", {})
        cols = [c.get("name", "").lower() for c in data.get("cols", [])]
        rows = data.get("rows", [])
    except Exception:
        return []

    if not cols or not rows:
        return []

    # Column name aliases → normalised key
    col_aliases = {
        # name variants
        "name": "name", "professional_name": "name", "nombre": "name",
        "full_name": "name", "professional": "name",
        # id
        "id": "professional_id", "professional_id": "professional_id",
        "worker_id": "professional_id", "user_id": "professional_id",
        # phone
        "phone": "phone", "telefono": "phone", "móvil": "phone",
        "phone_number": "phone", "mobile": "phone",
        # email
        "email": "email", "correo": "email",
        # facility
        "facility_name": "facility_name", "center": "facility_name",
        "hospital": "facility_name", "centro": "facility_name",
        # unit
        "unit": "unit", "livo_unit": "unit", "ward": "unit",
        "planta": "unit", "servicio": "unit",
        # shifts at facility
        "shifts_at_facility": "shifts_at_facility",
        "facility_shifts": "shifts_at_facility",
        "count": "shifts_at_facility",
        "shift_count": "shifts_at_facility",
        "num_shifts": "shifts_at_facility",
        "total": "shifts_at_facility",
        "repeater_count": "shifts_at_facility",
        # total shifts
        "total_shifts": "total_shifts",
        # last shift
        "last_shift": "last_shift_date", "last_shift_date": "last_shift_date",
        "last_date": "last_shift_date", "ultima_guardia": "last_shift_date",
        # role
        "professional_field": "role", "field": "role",
        "speciality": "role", "especialidad": "role",
    }

    profiles: list[dict] = []
    for row in rows:
        profile: dict = {}
        for i, val in enumerate(row):
            if i >= len(cols):
                break
            col = cols[i]
            norm_key = col_aliases.get(col, col)
            profile[norm_key] = val

        # Must have a name to be useful
        if not profile.get("name"):
            continue

        # Coerce shift counts to int
        for key in ("shifts_at_facility", "shifts_in_unit", "total_shifts"):
            try:
                profile[key] = int(profile.get(key) or 0)
            except (ValueError, TypeError):
                profile[key] = 0

        profiles.append(profile)

    return profiles
