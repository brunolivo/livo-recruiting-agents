"""
Healthcare Shift & Professional models for Livo critical-shift staffing.

Flow:
  Shift (description) → source professionals from Metabase (repeaters DB)
  → score by facility/unit history → generate Spanish outreach messages
"""

from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class HealthcareRole(str, Enum):
    MATRONA          = "Matrona"
    ENFERMERA        = "Enfermera/o"
    MEDICO           = "Médico/a"
    TECNICO          = "Técnico/a"
    AUXILIAR         = "Auxiliar de Enfermería"
    FISIOTERAPEUTA   = "Fisioterapeuta"
    CELADOR          = "Celador/a"
    FARMACEUTICO     = "Farmacéutico/a"


# Map from HealthcareRole → Metabase professional_field filter value
ROLE_TO_METABASE: dict[str, str] = {
    "Matrona":               "MIDWIVES",
    "Enfermera/o":           "NURSES",
    "Médico/a":              "DOCTORS",
    "Técnico/a":             "TECHNICIANS",
    "Auxiliar de Enfermería": "CARE_ASSISTANTS",
    "Fisioterapeuta":        "PHYSIOTHERAPISTS",
    "Celador/a":             "PORTERS",
    "Farmacéutico/a":        "PHARMACISTS",
}

# Map from free-text keywords (lowercase) → HealthcareRole
KEYWORD_TO_ROLE: dict[str, HealthcareRole] = {
    "matrona":        HealthcareRole.MATRONA,
    "matronas":       HealthcareRole.MATRONA,
    "midwife":        HealthcareRole.MATRONA,
    "midwives":       HealthcareRole.MATRONA,
    "enfermera":      HealthcareRole.ENFERMERA,
    "enfermero":      HealthcareRole.ENFERMERA,
    "nurse":          HealthcareRole.ENFERMERA,
    "nurses":         HealthcareRole.ENFERMERA,
    "médico":         HealthcareRole.MEDICO,
    "medico":         HealthcareRole.MEDICO,
    "doctor":         HealthcareRole.MEDICO,
    "doctors":        HealthcareRole.MEDICO,
    "técnico":        HealthcareRole.TECNICO,
    "tecnico":        HealthcareRole.TECNICO,
    "auxiliar":       HealthcareRole.AUXILIAR,
    "fisioterapeuta": HealthcareRole.FISIOTERAPEUTA,
    "celador":        HealthcareRole.CELADOR,
    "farmacéutico":   HealthcareRole.FARMACEUTICO,
}


class Shift(BaseModel):
    """A specific shift that needs to be covered."""
    role:             HealthcareRole
    facility_name:    str
    unit:             Optional[str] = None
    date_str:         str                    # human-readable, e.g. "22 de mayo"
    start_time:       str                    # "20:20"
    end_time:         str                    # "08:00"
    duration_hours:   float = 12.0
    notes:            Optional[str] = None
    raw_description:  Optional[str] = None   # original free-text

    @property
    def metabase_field(self) -> str:
        return ROLE_TO_METABASE.get(self.role.value, self.role.value.upper())

    @property
    def display_time(self) -> str:
        return f"{self.start_time}h – {self.end_time}h ({self.duration_hours:.0f}h)"

    @property
    def display_label(self) -> str:
        unit_part = f" · {self.unit}" if self.unit else ""
        return f"{self.role.value} — {self.date_str}, {self.display_time}{unit_part}"


class HealthcareProfessional(BaseModel):
    """A professional sourced from the Metabase repeaters database."""
    name:               str
    role:               HealthcareRole
    source:             str = "Metabase"
    professional_id:    Optional[str] = None
    phone:              Optional[str] = None
    email:              Optional[str] = None
    facility_name:      Optional[str] = None
    unit:               Optional[str] = None
    shifts_at_facility: int = 0      # times worked at the target facility
    shifts_in_unit:     int = 0      # times worked in the specific unit
    total_shifts:       int = 0      # total shifts on platform
    last_shift_date:    Optional[str] = None
    location:           Optional[str] = None


class ScoredProfessional(HealthcareProfessional):
    """Professional after scoring — ready to filter and rank."""
    availability_score: float = 0.0   # 0-10: estimated availability signal
    experience_score:   float = 0.0   # 0-10: facility/unit familiarity
    fit_score:          float = 0.0   # 0-10: overall weighted score
    scoring_rationale:  Optional[str] = None
    recommended:        bool = False


class ContactedProfessional(ScoredProfessional):
    """Professional with outreach message ready to send."""
    message_body:    Optional[str] = None
    contact_channel: str = "WhatsApp"


class ShiftPipelineResult(BaseModel):
    """Full output of the shift staffing pipeline."""
    shift:         Shift
    professionals: list[ContactedProfessional] = Field(default_factory=list)
    stats:         dict = Field(default_factory=dict)
