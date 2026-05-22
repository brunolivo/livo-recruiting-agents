"""
Shift Outreach Agent — generates personalised Spanish WhatsApp messages
inviting healthcare professionals to cover a critical shift.

All messages are written in Spanish. Tone: warm, direct, professional.
Channel: WhatsApp (short, clear, emoji-friendly).
"""

import json
from models.shift import Shift, ScoredProfessional, ContactedProfessional
from agents.base_agent import run_agent

SYSTEM_PROMPT = """Eres el equipo de operaciones de Livo, la plataforma de personal sanitario en España.
Tu objetivo es redactar mensajes de WhatsApp cortos y personalizados para invitar a profesionales
sanitarios a cubrir turnos urgentes.

Estilo:
- Tono cálido y directo, como si fuera un colega de confianza
- Menciona los turnos previos del profesional en ese centro si los hay (genera confianza)
- Incluye los detalles clave del turno: fecha, horario, duración, centro y unidad (si aplica)
- Termina con una llamada a la acción clara: ¿Puedes confirmarlo?
- Usa algún emoji de forma natural (🏥 📅 👋 💙) pero sin exagerar
- Máximo 120 palabras por mensaje
- NO uses textos genéricos — hazlo personal"""


def generate_outreach_batch(
    professionals: list[ScoredProfessional],
    shift: Shift,
) -> list[ContactedProfessional]:
    """
    Generate personalised Spanish WhatsApp messages for all recommended professionals.
    Batched into a single LLM call.
    """
    targets = [p for p in professionals if p.recommended]
    if not targets:
        return _build_without_messages(professionals)

    profiles = [
        {
            "index":               i,
            "name":                p.name,
            "shifts_at_facility":  p.shifts_at_facility,
            "shifts_in_unit":      p.shifts_in_unit,
            "last_shift_date":     p.last_shift_date or "",
        }
        for i, p in enumerate(targets)
    ]

    unit_line = f"\nUnidad: {shift.unit}" if shift.unit else ""

    prompt = f"""Redacta mensajes de WhatsApp personalizados para estos {len(targets)} profesionales.

TURNO A CUBRIR:
Rol: {shift.role.value}
Centro: {shift.facility_name}{unit_line}
Fecha: {shift.date_str}
Horario: {shift.start_time}h – {shift.end_time}h ({shift.duration_hours:.0f} horas)

PROFESIONALES:
{json.dumps(profiles, indent=2, ensure_ascii=False)}

Instrucciones:
- Si "shifts_at_facility" > 0: menciona que ya han trabajado N veces en ese centro
- Si "shifts_at_facility" == 0: no menciones historial, enfócate en la oportunidad
- Si "last_shift_date" tiene valor: puedes mencionar que han trabajado recientemente
- Usa el nombre de pila (primera palabra del nombre)
- Mensaje máximo 120 palabras

Devuelve SOLO un array JSON:
[
  {{
    "index": 0,
    "message_body": "texto del mensaje aquí"
  }}
]"""

    result = run_agent(
        system_prompt=SYSTEM_PROMPT,
        user_message=prompt,
        agent_name=f"Shift Outreach ({shift.role.value})",
        use_web_search=False,
    )

    msg_map: dict[int, str] = {}
    try:
        clean = result.strip()
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        start, end = clean.find("["), clean.rfind("]") + 1
        if start >= 0 and end > start:
            items = json.loads(clean[start:end])
            msg_map = {item["index"]: item["message_body"] for item in items if "index" in item}
    except Exception:
        pass

    # If LLM failed, use a default template
    def _default_msg(p: ScoredProfessional) -> str:
        first_name = p.name.split()[0] if p.name else "Hola"
        history_line = (
            f"Ya has trabajado {p.shifts_at_facility} veces en {shift.facility_name}. "
            if p.shifts_at_facility > 0 else ""
        )
        unit_line = f"Unidad: {shift.unit}\n" if shift.unit else ""
        return (
            f"¡Hola {first_name}! 👋\n\n"
            f"Tenemos un turno urgente que necesita cobertura:\n\n"
            f"🏥 {shift.facility_name}\n"
            f"{unit_line}"
            f"📅 {shift.date_str} · {shift.start_time}h – {shift.end_time}h "
            f"({shift.duration_hours:.0f}h)\n"
            f"👩‍⚕️ {shift.role.value}\n\n"
            f"{history_line}"
            f"¿Estarías disponible para cubrirlo?\n\n"
            f"Si confirmas, te enviamos todos los detalles enseguida. ¡Gracias! 💙\n"
            f"Equipo Livo"
        )

    contacted: list[ContactedProfessional] = []
    for i, p in enumerate(targets):
        msg = msg_map.get(i) or _default_msg(p)
        contacted.append(ContactedProfessional(
            **p.model_dump(),
            message_body=msg,
            contact_channel="WhatsApp",
        ))

    # Append non-recommended without messages
    target_names = {p.name for p in targets}
    for p in professionals:
        if p.name not in target_names:
            contacted.append(ContactedProfessional(**p.model_dump(), contact_channel="WhatsApp"))

    return contacted


def _build_without_messages(
    professionals: list[ScoredProfessional],
) -> list[ContactedProfessional]:
    return [ContactedProfessional(**p.model_dump(), contact_channel="WhatsApp") for p in professionals]
