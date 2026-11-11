"""Correo: Gmail (API oficial, OAuth de escritorio) y Outlook (Microsoft Graph,
device code). Leer/buscar/borrador = safe. Enviar = sensitive.

Setup:
  Gmail   -> crea credenciales "Desktop app" en Google Cloud, guarda como
             ~/.lay/gmail_credentials.json. Primer uso abre el navegador.
  Outlook -> registra una app en Entra ID (cuentas personales + org),
             pon OUTLOOK_CLIENT_ID en .env. Primer uso muestra un código.
"""

from __future__ import annotations

import base64
import json
import os
from email.mime.text import MIMEText

from lay_core.config import DATA_DIR
from lay_core.seguridad import sensible

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
GRAPH = "https://graph.microsoft.com/v1.0"


# ---------------- Gmail ----------------
def _gmail():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    tok = DATA_DIR / "gmail_token.json"
    creds = Credentials.from_authorized_user_file(str(tok), GMAIL_SCOPES) if tok.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(DATA_DIR / "gmail_credentials.json"), GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        tok.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _gmail_resumen(svc, mid: str) -> dict:
    m = (
        svc.users()
        .messages()
        .get(userId="me", id=mid, format="metadata", metadataHeaders=["From", "Subject", "Date"])
        .execute()
    )
    h = {x["name"]: x["value"] for x in m["payload"]["headers"]}
    return {
        "id": mid,
        "de": h.get("From"),
        "asunto": h.get("Subject"),
        "fecha": h.get("Date"),
        "extracto": m.get("snippet", ""),
    }


def gmail_buscar(consulta: str = "is:unread", limite: int = 10) -> list[dict]:
    svc = _gmail()
    r = svc.users().messages().list(userId="me", q=consulta, maxResults=limite).execute()
    return [_gmail_resumen(svc, m["id"]) for m in r.get("messages", [])]


def gmail_borrador(para: str, asunto: str, cuerpo: str) -> dict:
    svc = _gmail()
    msg = MIMEText(cuerpo, "plain", "utf-8")
    msg["to"], msg["subject"] = para, asunto
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    d = svc.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
    return {"ok": True, "borrador_id": d["id"]}


@sensible("LAY va a ENVIAR un correo desde Gmail")
def gmail_enviar(para: str, asunto: str, cuerpo: str) -> dict:
    svc = _gmail()
    msg = MIMEText(cuerpo, "plain", "utf-8")
    msg["to"], msg["subject"] = para, asunto
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    r = svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    return {"ok": True, "id": r["id"]}


def gmail_archivar(mensaje_id: str) -> dict:
    _gmail().users().messages().modify(userId="me", id=mensaje_id, body={"removeLabelIds": ["INBOX"]}).execute()
    return {"ok": True}


# ---------------- Outlook (Graph) ----------------
def _graph_token() -> str:
    import msal

    cache = msal.SerializableTokenCache()
    cfile = DATA_DIR / "outlook_cache.json"
    if cfile.exists():
        cache.deserialize(cfile.read_text())
    app = msal.PublicClientApplication(
        os.environ["OUTLOOK_CLIENT_ID"], authority="https://login.microsoftonline.com/common", token_cache=cache
    )
    scopes = ["Mail.ReadWrite", "Mail.Send", "Calendars.Read"]
    accts = app.get_accounts()
    res = app.acquire_token_silent(scopes, account=accts[0]) if accts else None
    if not res:
        flow = app.initiate_device_flow(scopes=scopes)
        print(flow["message"])  # se muestra en consola / HUD
        res = app.acquire_token_by_device_flow(flow)
    if cache.has_state_changed:
        cfile.write_text(cache.serialize())
    return res["access_token"]


def _graph(method: str, path: str, **kw):
    import httpx

    r = httpx.request(method, GRAPH + path, headers={"Authorization": f"Bearer {_graph_token()}"}, timeout=20, **kw)
    r.raise_for_status()
    return r.json() if r.content else {}


def outlook_no_leidos(limite: int = 10) -> list[dict]:
    d = _graph(
        "GET",
        "/me/mailFolders/inbox/messages",
        params={
            "$filter": "isRead eq false",
            "$top": limite,
            "$select": "id,from,subject,receivedDateTime,bodyPreview",
        },
    )
    return [
        {
            "id": m["id"],
            "de": m["from"]["emailAddress"]["address"],
            "asunto": m["subject"],
            "fecha": m["receivedDateTime"],
            "extracto": m["bodyPreview"],
        }
        for m in d.get("value", [])
    ]


def outlook_agenda(dias: int = 3) -> list[dict]:
    from datetime import datetime, timedelta, timezone

    ini = datetime.now(timezone.utc)
    fin = ini + timedelta(days=dias)
    d = _graph(
        "GET",
        "/me/calendarView",
        params={
            "startDateTime": ini.isoformat(),
            "endDateTime": fin.isoformat(),
            "$select": "subject,start,end,location",
            "$orderby": "start/dateTime",
        },
    )
    return [
        {
            "asunto": e["subject"],
            "inicio": e["start"]["dateTime"],
            "fin": e["end"]["dateTime"],
            "lugar": (e.get("location") or {}).get("displayName"),
        }
        for e in d.get("value", [])
    ]


@sensible("LAY va a ENVIAR un correo desde Outlook")
def outlook_enviar(para: str, asunto: str, cuerpo: str) -> dict:
    _graph(
        "POST",
        "/me/sendMail",
        content=json.dumps(
            {
                "message": {
                    "subject": asunto,
                    "body": {"contentType": "Text", "content": cuerpo},
                    "toRecipients": [{"emailAddress": {"address": para}}],
                }
            }
        ),
    )
    return {"ok": True}
