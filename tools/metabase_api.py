"""
Metabase API client — queries the Livo repeaters database.

Question 12652: "Repeaters by facility and units fields"
URL: https://livo.metabaseapp.com/question/12652

Confirmed working parameter format (verified against live API 2026-05-22):
  - type:   "string/="
  - target: ["dimension", ["template-tag", "<name>"]]
  - value:  ["value"]   ← must be an ARRAY, not a string
  - id:     UUID from the card's parameters list (required for filtering to work)

Parameter IDs for card 12652:
  professional_field  → 524b1355-7318-4675-8c82-6e188f4376af
  facility_name       → 4dc34135-30a0-4857-b874-1ea9c8107662
  livo_unit           → 550dd952-1569-453a-ae49-48e8d884dd56

Response columns (flat JSON array from /query/json):
  professional_id, first_name, last_name, phone_number,
  total_shifts, first_shift, last_shift

Auth: METABASE_USERNAME + METABASE_PASSWORD in .env (session-based)
      or METABASE_API_KEY (Metabase 47+)
"""

import os
import json
import ssl
import urllib.request
import urllib.error
from typing import Optional

METABASE_URL     = os.getenv("METABASE_URL", "https://livo.metabaseapp.com")
METABASE_USER    = os.getenv("METABASE_USERNAME", "")
METABASE_PASS    = os.getenv("METABASE_PASSWORD", "")
METABASE_API_KEY = os.getenv("METABASE_API_KEY", "")

REPEATERS_CARD_ID = 12652

# Confirmed parameter UUIDs for card 12652 (from /api/card/12652 metadata)
_PARAM_IDS = {
    "professional_field": "524b1355-7318-4675-8c82-6e188f4376af",
    "facility_name":      "4dc34135-30a0-4857-b874-1ea9c8107662",
    "livo_unit":          "550dd952-1569-453a-ae49-48e8d884dd56",
}

_ssl_ctx = ssl.create_default_context()

# Session token cache
_session_token: Optional[str] = None


# ── Auth ─────────────────────────────────────────────────────────────────────

def _get_headers() -> dict:
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
        payload = json.dumps({"username": METABASE_USER, "password": METABASE_PASS}).encode()
        req = urllib.request.Request(
            f"{METABASE_URL}/api/session",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15, context=_ssl_ctx) as resp:
            _session_token = json.loads(resp.read().decode()).get("id")
            return _session_token
    except Exception:
        return None


def _reset_session():
    """Force re-authentication on next call (call if we get a 401)."""
    global _session_token
    _session_token = None


# ── Public entry point ────────────────────────────────────────────────────────

def query_repeaters(
    facility_name: str,
    professional_field: str,
    unit: str = "",
) -> list[dict]:
    """
    Query card 12652 (repeaters) filtered by facility, professional field, and optional unit.
    Returns normalised list of professional profile dicts.

    Returns [] if Metabase credentials are not configured.
    """
    if not METABASE_API_KEY and not (METABASE_USER and METABASE_PASS):
        return []

    raw = _run_card(
        facility_name=facility_name,
        professional_field=professional_field,
        unit=unit,
    )
    return _normalise(raw)


# ── Internal ──────────────────────────────────────────────────────────────────

def _build_parameters(
    facility_name: str,
    professional_field: str,
    unit: str,
) -> list[dict]:
    """
    Build the parameters array for the Metabase card query.

    Rules (confirmed by live testing):
    - type must be "string/="
    - target must be ["dimension", ["template-tag", "<name>"]]
    - value must be a LIST (array), not a plain string
    - id must be the UUID from the card's parameters list
    - Only include a parameter if it has a non-empty value
      (omitting it lets the [[AND {{tag}}]] block be skipped = no filter)
    """
    params = []

    if professional_field:
        params.append({
            "type":   "string/=",
            "id":     _PARAM_IDS["professional_field"],
            "target": ["dimension", ["template-tag", "professional_field"]],
            "value":  [professional_field],
        })

    if facility_name:
        params.append({
            "type":   "string/=",
            "id":     _PARAM_IDS["facility_name"],
            "target": ["dimension", ["template-tag", "facility_name"]],
            "value":  [facility_name],
        })

    if unit:
        params.append({
            "type":   "string/=",
            "id":     _PARAM_IDS["livo_unit"],
            "target": ["dimension", ["template-tag", "livo_unit"]],
            "value":  [unit],
        })

    return params


def _run_card(
    facility_name: str,
    professional_field: str,
    unit: str,
    retry: bool = True,
) -> list[dict]:
    """POST /api/card/{id}/query/json — synchronous, returns flat JSON array."""
    parameters = _build_parameters(facility_name, professional_field, unit)
    body = json.dumps({"ignore_cache": False, "parameters": parameters}).encode()

    headers = _get_headers()
    req = urllib.request.Request(
        f"{METABASE_URL}/api/card/{REPEATERS_CARD_ID}/query/json",
        data=body,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30, context=_ssl_ctx) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        if e.code == 401 and retry:
            # Session expired — re-authenticate and try once more
            _reset_session()
            return _run_card(facility_name, professional_field, unit, retry=False)
        return []
    except Exception:
        return []


def _normalise(rows: list[dict]) -> list[dict]:
    """
    Convert raw Metabase rows into the standard profile dict format
    used throughout the pipeline.

    Raw columns: professional_id, first_name, last_name, phone_number,
                 total_shifts, first_shift, last_shift
    """
    profiles: list[dict] = []
    for row in rows:
        first = (row.get("first_name") or "").strip()
        last  = (row.get("last_name")  or "").strip()
        name  = f"{first} {last}".strip()
        if not name:
            continue

        # Extract date part from ISO datetime  "2026-05-31T12:00:00" → "2026-05-31"
        last_shift_raw = row.get("last_shift") or ""
        last_shift_date = str(last_shift_raw)[:10] if last_shift_raw else ""

        profiles.append({
            "name":               name,
            "professional_id":    str(row.get("professional_id") or ""),
            "phone":              row.get("phone_number") or None,
            "email":              row.get("email") or None,
            "shifts_at_facility": int(row.get("total_shifts") or 0),
            "shifts_in_unit":     0,   # card doesn't break out unit count
            "total_shifts":       int(row.get("total_shifts") or 0),
            "last_shift_date":    last_shift_date,
        })

    return profiles
