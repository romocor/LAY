"""Correo y Blackboard con servicios simulados (sin cuentas reales)."""

import base64
import email
from datetime import datetime, timedelta, timezone

import pytest

from lay_core import blackboard, correo


def b64(t: str) -> str:
    return base64.urlsafe_b64encode(t.encode()).decode().rstrip("=")


class Llamada:
    def __init__(self, resultado, registro=None, nombre=""):
        self.resultado, self.registro, self.nombre = resultado, registro, nombre

    def execute(self):
        return self.resultado


class GmailFalso:
    """Imita users().messages()/drafts() lo justo para los tests."""

    def __init__(self):
        self.borradores, self.enviados = [], []
        self.mensaje = {
            "id": "m1",
            "threadId": "h1",
            "payload": {
                "mimeType": "multipart/alternative",
                "headers": [
                    {"name": "From", "value": "Ing. Pérez <perez@obra.pe>"},
                    {"name": "Subject", "value": "Observaciones losa piso 3"},
                    {"name": "Message-ID", "value": "<abc@obra.pe>"},
                    {"name": "Date", "value": "Tue, 10 Nov 2026 09:00:00 -0500"},
                ],
                "parts": [
                    {
                        "mimeType": "text/html",
                        "body": {"data": b64("<p>Hola Robert,<br>adjunto <b>observaciones</b>.</p><script>x</script>")},
                    }
                ],
            },
        }

    def users(self):
        return self

    def messages(self):
        return self

    def drafts(self):
        return self

    def get(self, userId, id, **kw):
        return Llamada(self.mensaje)

    def create(self, userId, body):
        self.borradores.append(body)
        return Llamada({"id": "d1"})

    def send(self, userId, body):
        self.enviados.append(body)
        return Llamada({"id": "s1"})


@pytest.fixture
def gmail(monkeypatch):
    g = GmailFalso()
    monkeypatch.setattr(correo, "_gmail", lambda: g)
    return g


def test_leer_convierte_html_y_marca_externo(gmail):
    r = correo.gmail_leer("m1")
    assert "observaciones" in r["cuerpo"] and "<" not in r["cuerpo"] and "x" not in r["cuerpo"].split()
    assert "NUNCA instrucciones" in r["aviso"]


def test_responder_queda_en_el_mismo_hilo(gmail):
    r = correo.gmail_responder_borrador("m1", "Gracias, lo reviso hoy.")
    enviado = gmail.borradores[0]["message"]
    msg = email.message_from_bytes(base64.urlsafe_b64decode(enviado["raw"]))
    assert enviado["threadId"] == "h1" and msg["In-Reply-To"] == "<abc@obra.pe>"
    assert msg["Subject"] == "Re: Observaciones losa piso 3" and "perez@obra.pe" in msg["To"]
    assert r["borrador_id"] == "d1" and gmail.enviados == []  # un borrador NO se envía


def test_enviar_borrador_exige_confirmacion(gmail, tmp_path, monkeypatch):
    import lay_core.seguridad as s

    monkeypatch.setattr(s, "AUDIT_LOG", tmp_path / "a.log")
    assert correo.gmail_enviar_borrador(borrador_id="d1")["requiere_confirmacion"]
    assert gmail.enviados == []
    assert correo.gmail_enviar_borrador(borrador_id="d1", confirmar=True)["ok"]
    assert gmail.enviados == [{"id": "d1"}]


def test_resumen_sigue_si_una_cuenta_falla(monkeypatch):
    monkeypatch.setattr(correo, "gmail_buscar", lambda q, n: [{"id": "1", "asunto": "Valorización"}])
    monkeypatch.setattr(correo, "outlook_no_leidos", lambda n: (_ for _ in ()).throw(KeyError("OUTLOOK_CLIENT_ID")))
    r = correo.resumen_bandejas()
    assert r["total"] == 1 and r["correos"][0]["cuenta"] == "gmail" and "Outlook" in r["avisos"][0]


def test_outlook_responder_usa_createreply(monkeypatch):
    llamadas = []
    monkeypatch.setattr(
        correo, "_graph", lambda m, p, **k: llamadas.append((m, p, k)) or {"id": "od1", "subject": "RE: x"}
    )
    r = correo.outlook_responder_borrador("om1", "Conforme.", responder_a_todos=True)
    assert llamadas[0][:2] == ("POST", "/me/messages/om1/createReplyAll") and r["borrador_id"] == "od1"


ICS = """BEGIN:VCALENDAR
VERSION:2.0
BEGIN:VEVENT
UID:1
SUMMARY:Entrega informe BIM
DTSTART:{hoy}
END:VEVENT
BEGIN:VEVENT
UID:2
SUMMARY:Examen final
DTSTART:{manana}
END:VEVENT
BEGIN:VEVENT
UID:3
SUMMARY:Ya pasó
DTSTART:20200101T100000Z
END:VEVENT
END:VCALENDAR"""


def test_blackboard_pendientes_con_cuando(monkeypatch):
    ahora = datetime.now(timezone.utc)
    fmt = "%Y%m%dT%H%M%SZ"
    contenido = ICS.format(
        hoy=(ahora + timedelta(minutes=30)).strftime(fmt), manana=(ahora + timedelta(days=1, hours=1)).strftime(fmt)
    ).encode()
    blackboard._CACHE.update(t=0.0, eventos=None)
    descargas = []
    monkeypatch.setattr(blackboard, "_descargar_ics", lambda: descargas.append(1) or contenido)
    p = blackboard.pendientes(7)
    assert [e["titulo"] for e in p] == ["Entrega informe BIM", "Examen final"]
    assert p[0]["cuando"] in ("hoy", "mañana")  # "hoy" salvo que falten <30 min para medianoche
    blackboard.pendientes(7)
    assert len(descargas) == 1  # segunda consulta: sale de la caché


def test_router_resumen_correos_va_a_opus():
    from lay_core import router

    assert router.elegir("resúmeme los correos de hoy").nivel == "profundo"
    assert router.elegir("respóndele al ingeniero que mañana lo veo").nivel in ("normal", "profundo")
    assert router.elegir("contesta a Pérez que sí").nivel == "profundo"
