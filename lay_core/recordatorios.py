"""Recordatorios, alarmas y temporizadores. Se guardan en ~/.lay/recordatorios.json y el hub
los dispara (LAY lo dice en voz alta + aviso en el HUD + notificación de Windows).

Entiende: "en 10 minutos", "en 1 hora y media", "a las 15:30", "a las 3 de la tarde",
"mañana a las 9", "el viernes a las 8", "2026-11-20 10:00".
"""

from __future__ import annotations

import json
import re
import threading
import time
import uuid
from datetime import datetime, timedelta

from lay_core.config import DATA_DIR

ARCHIVO = DATA_DIR / "recordatorios.json"
_lock = threading.Lock()
DIAS = {
    "lunes": 0,
    "martes": 1,
    "miércoles": 2,
    "miercoles": 2,
    "jueves": 3,
    "viernes": 4,
    "sábado": 5,
    "sabado": 5,
    "domingo": 6,
}
NUMEROS = {
    "un": 1,
    "una": 1,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "diez": 10,
    "quince": 15,
    "veinte": 20,
    "treinta": 30,
    "media": 0.5,
    "cuarto": 0.25,
}


def _num(t: str) -> float:
    t = t.replace(",", ".")
    return float(t) if re.fullmatch(r"\d+(\.\d+)?", t) else NUMEROS.get(t, 0)


def interpretar(cuando: str, ahora: datetime | None = None) -> datetime:
    """Convierte lenguaje natural en fecha y hora. ValueError si no se entiende."""
    ahora = ahora or datetime.now()
    t = cuando.lower().strip().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    t = t.replace("medianoche", "a las 0").replace("mediodia", "a las 12")

    m = re.fullmatch(r"(\d{4}-\d{2}-\d{2})[ t](\d{1,2}):(\d{2})", t)
    if m:
        return datetime.fromisoformat(f"{m.group(1)} {int(m.group(2)):02d}:{m.group(3)}")

    # "en 10 minutos", "en una hora y media", "en 2 horas 15 minutos", "dentro de 30 segundos"
    if re.match(r"^(en|dentro de)\b", t):
        total = timedelta()
        for cant, unidad in re.findall(
            r"(\d+(?:[.,]\d+)?|un|una|uno|dos|tres|cuatro|cinco|diez|quince|veinte|treinta)\s*"
            r"(segundos?|seg|minutos?|min|horas?|h|dias?)",
            t,
        ):
            n = _num(cant)
            if unidad.startswith("seg"):
                total += timedelta(seconds=n)
            elif unidad.startswith("min"):
                total += timedelta(minutes=n)
            elif unidad.startswith("h"):
                total += timedelta(hours=n)
            else:
                total += timedelta(days=n)
        if re.search(r"\by media\b", t):
            total += timedelta(minutes=30) if re.search(r"hora", t) else timedelta(seconds=30)
        if total.total_seconds() <= 0:
            raise ValueError(f"No entendí '{cuando}'")
        return ahora + total

    dia = ahora.date()
    if "pasado mañana" in t or "pasado manana" in t:
        dia += timedelta(days=2)
    elif "mañana" in t or "manana" in t:
        dia += timedelta(days=1)
    else:
        for nombre, n in DIAS.items():
            if re.search(rf"\b{nombre}\b", t):
                dias = (n - ahora.weekday()) % 7 or 7
                dia += timedelta(days=dias)
                break
    m = re.search(r"(\d{1,2})(?:[:.h](\d{2}))?\s*(am|pm|de la mañana|de la manana|de la tarde|de la noche)?", t)
    if not m:
        if dia != ahora.date():
            return datetime.combine(dia, datetime.min.time()).replace(hour=9)  # "mañana" a secas -> 9:00
        raise ValueError(f"No entendí '{cuando}'")
    hora, minuto, sufijo = int(m.group(1)), int(m.group(2) or 0), m.group(3) or ""
    if ("pm" in sufijo or "tarde" in sufijo or "noche" in sufijo) and hora < 12:
        hora += 12
    if ("am" in sufijo or "mañana" in sufijo or "manana" in sufijo) and hora == 12:
        hora = 0
    momento = datetime.combine(dia, datetime.min.time()).replace(hour=hora % 24, minute=minuto)
    if momento <= ahora and dia == ahora.date():
        # "a las 3" dicho a las 4 pm -> las 3 de la madrugada no: probar 15:00, si no mañana
        if hora < 12 and not sufijo and momento.replace(hour=hora + 12) > ahora:
            momento = momento.replace(hour=hora + 12)
        else:
            momento += timedelta(days=1)
    return momento


def _leer() -> list[dict]:
    try:
        return json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _escribir(datos: list[dict]) -> None:
    ARCHIVO.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def crear(mensaje: str, cuando: str, repetir: str = "") -> dict:
    """repetir: '' | 'diario' | 'semanal'."""
    momento = interpretar(cuando)
    r = {
        "id": uuid.uuid4().hex[:6],
        "mensaje": mensaje.strip()[:200],
        "momento": momento.isoformat(timespec="minutes"),
        "repetir": repetir if repetir in ("diario", "semanal") else "",
    }
    with _lock:
        datos = _leer()
        datos.append(r)
        _escribir(datos)
    falta = momento - datetime.now()
    return {
        "ok": True,
        **r,
        "cuando_texto": momento.strftime("%A %d/%m a las %H:%M"),
        "falta_min": max(0, round(falta.total_seconds() / 60)),
    }


def listar() -> list[dict]:
    datos = sorted(_leer(), key=lambda r: r["momento"])
    return [{**r, "cuando_texto": datetime.fromisoformat(r["momento"]).strftime("%a %d/%m %H:%M")} for r in datos]


def borrar(id_o_texto: str) -> dict:
    with _lock:
        datos = _leer()
        q = id_o_texto.lower().strip()
        resto = [r for r in datos if r["id"] != q and q not in r["mensaje"].lower()]
        if len(resto) == len(datos):
            return {"error": f"No encontré un recordatorio '{id_o_texto}'."}
        _escribir(resto)
    return {"ok": True, "borrados": len(datos) - len(resto)}


def vencidos(ahora: datetime | None = None) -> list[dict]:
    """Saca los que ya tocan (y reprograma los repetitivos). Lo llama el hub cada 15 s."""
    ahora = ahora or datetime.now()
    with _lock:
        datos, toca, quedan = _leer(), [], []
        for r in datos:
            m = datetime.fromisoformat(r["momento"])
            if m <= ahora:
                toca.append(r)
                if r.get("repetir"):
                    paso = timedelta(days=1 if r["repetir"] == "diario" else 7)
                    while m <= ahora:
                        m += paso
                    quedan.append({**r, "momento": m.isoformat(timespec="minutes")})
            else:
                quedan.append(r)
        if toca:
            _escribir(quedan)
    return toca


def notificar_windows(titulo: str, texto: str) -> None:
    """Notificación nativa de Windows (sin dependencias)."""
    import platform
    import subprocess

    if platform.system() != "Windows":
        return
    limpio = lambda s: s.replace("'", "").replace('"', "")[:180]  # noqa: E731
    ps = (
        "[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] > $null;"
        "$t=[Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent(2);"
        f"$x=$t.GetElementsByTagName('text');$x[0].AppendChild($t.CreateTextNode('{limpio(titulo)}'))>$null;"
        f"$x[1].AppendChild($t.CreateTextNode('{limpio(texto)}'))>$null;"
        "[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('LAY').Show("
        "[Windows.UI.Notifications.ToastNotification]::new($t))"
    )
    subprocess.Popen(
        ["powershell", "-NoProfile", "-Command", ps], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
    )


def esperar(segundos: float) -> None:
    time.sleep(segundos)
