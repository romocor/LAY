"""Blackboard Learn.

Camino 1 (funciona ya, sin permisos de admin): el feed iCal del calendario.
  Blackboard -> Calendario -> ⚙ -> "Compartir calendario" -> copia la URL .ics
  y ponla en .env como BLACKBOARD_ICS_URL. Da entregas, exámenes y fechas.

Camino 2 (opcional): REST API (requiere app registrada por la universidad).
  BLACKBOARD_BASE_URL + BLACKBOARD_TOKEN (3-legged OAuth).
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone

import httpx


def _ics() -> list[dict]:
    from icalendar import Calendar

    url = os.environ.get("BLACKBOARD_ICS_URL")
    if not url:
        raise RuntimeError("Falta BLACKBOARD_ICS_URL en .env (ver docstring de lay_core/blackboard.py)")
    cal = Calendar.from_ical(httpx.get(url, timeout=20, follow_redirects=True).content)
    eventos = []
    for ev in cal.walk("VEVENT"):
        ini = ev.decoded("DTSTART")
        if isinstance(ini, date) and not isinstance(ini, datetime):
            ini = datetime.combine(ini, datetime.min.time(), tzinfo=timezone.utc)
        if ini.tzinfo is None:
            ini = ini.replace(tzinfo=timezone.utc)
        eventos.append(
            {
                "titulo": str(ev.get("SUMMARY", "")),
                "fecha": ini,
                "curso": str(ev.get("CATEGORIES", "") or ev.get("LOCATION", "")),
                "detalle": str(ev.get("DESCRIPTION", ""))[:300],
            }
        )
    return eventos


def pendientes(dias: int = 14) -> list[dict]:
    ahora = datetime.now(timezone.utc)
    fin = ahora + timedelta(days=dias)
    evs = [e for e in _ics() if ahora <= e["fecha"] <= fin]
    evs.sort(key=lambda e: e["fecha"])
    return [
        {**e, "fecha": e["fecha"].astimezone().strftime("%a %d/%m %H:%M"), "dias_restantes": (e["fecha"] - ahora).days}
        for e in evs
    ]


def cursos_rest() -> list[dict]:
    base, tok = os.environ.get("BLACKBOARD_BASE_URL"), os.environ.get("BLACKBOARD_TOKEN")
    if not (base and tok):
        raise RuntimeError("REST de Blackboard no configurado; usa pendientes() con el feed iCal")
    r = httpx.get(
        f"{base}/learn/api/public/v1/users/me/courses", headers={"Authorization": f"Bearer {tok}"}, timeout=20
    )
    r.raise_for_status()
    return r.json().get("results", [])
