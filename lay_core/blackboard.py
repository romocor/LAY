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

_CACHE: dict = {"t": 0.0, "eventos": None}
CACHE_S = 600  # el feed de Blackboard cambia poco; evita descargarlo en cada pregunta


def _ics() -> list[dict]:
    import time

    if _CACHE["eventos"] is not None and time.time() - _CACHE["t"] < CACHE_S:
        return _CACHE["eventos"]
    eventos = parsear_ics(_descargar_ics())
    _CACHE.update(t=time.time(), eventos=eventos)
    return eventos


def _descargar_ics() -> bytes:
    url = os.environ.get("BLACKBOARD_ICS_URL")
    if not url:
        raise RuntimeError("Falta BLACKBOARD_ICS_URL en .env (ver docstring de lay_core/blackboard.py)")
    return httpx.get(url, timeout=20, follow_redirects=True).content


def parsear_ics(contenido: bytes) -> list[dict]:
    from icalendar import Calendar

    cal = Calendar.from_ical(contenido)
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
    """Entregas/exámenes de los próximos `dias`, ordenados, con "hoy / mañana / en N días"."""
    ahora = datetime.now(timezone.utc)
    fin = ahora + timedelta(days=dias)
    evs = sorted((e for e in _ics() if ahora <= e["fecha"] <= fin), key=lambda e: e["fecha"])
    hoy = ahora.astimezone().date()
    out = []
    for e in evs:
        d = (e["fecha"].astimezone().date() - hoy).days
        cuando = "hoy" if d == 0 else "mañana" if d == 1 else f"en {d} días"
        out.append(
            {**e, "fecha": e["fecha"].astimezone().strftime("%d/%m %H:%M"), "cuando": cuando, "dias_restantes": d}
        )
    return out


def cursos_rest() -> list[dict]:
    base, tok = os.environ.get("BLACKBOARD_BASE_URL"), os.environ.get("BLACKBOARD_TOKEN")
    if not (base and tok):
        raise RuntimeError("REST de Blackboard no configurado; usa pendientes() con el feed iCal")
    r = httpx.get(
        f"{base}/learn/api/public/v1/users/me/courses", headers={"Authorization": f"Bearer {tok}"}, timeout=20
    )
    r.raise_for_status()
    return r.json().get("results", [])
