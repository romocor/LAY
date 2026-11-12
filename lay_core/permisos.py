"""Permisos de Windows que limitan a LAY, y el modo administrador.

Por qué existe: aunque Robert es administrador, con UAC cada programa corre SIN privilegios. Windows
(UIPI) impide que un programa normal mande clics/teclas o lea con UI Automation ventanas que corren
como administrador: Administrador de tareas, instaladores, regedit, apps abiertas "como admin".
Solución opcional: arrancar LAY elevado con una tarea programada (pide UAC UNA vez al activarla).

Lo que NINGÚN programa puede (ni debe) hacer: aceptar la ventana de UAC (escritorio seguro).

Seguridad: esto solo se activa con el botón de Configuración (no hay herramienta MCP: la IA no
puede elevarse sola). Las acciones sensibles siguen pidiendo confirmación igual.
"""

from __future__ import annotations

import os
import subprocess
import sys

TAREA = "LAY (administrador)"
ES_WINDOWS = os.name == "nt"


def es_admin() -> bool:
    if not ES_WINDOWS:
        return os.geteuid() == 0 if hasattr(os, "geteuid") else False
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:  # noqa: BLE001
        return False


def _ps(cmd: str) -> str:
    try:
        return subprocess.run(
            ["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=20
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def estado() -> dict:
    """Qué podría estar bloqueando a LAY en esta PC."""
    if not ES_WINDOWS:
        return {"windows": False}
    uac = _ps(
        "$u=Get-ItemProperty 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System';"
        '"$($u.EnableLUA)|$($u.ConsentPromptBehaviorAdmin)"'
    ).split("|")
    carpetas = _ps("try{(Get-MpPreference).EnableControlledFolderAccess}catch{''}")
    tarea = bool(_ps(f"Get-ScheduledTask -TaskName '{TAREA}' -ErrorAction SilentlyContinue | Select -Expand TaskName"))
    camara = _ps(
        "(Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\"
        "ConsentStore\\webcam\\NonPackaged' -ErrorAction SilentlyContinue).Value"
    )
    micro = _ps(
        "(Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\CapabilityAccessManager\\"
        "ConsentStore\\microphone\\NonPackaged' -ErrorAction SilentlyContinue).Value"
    )
    avisos = []
    if not es_admin():
        avisos.append(
            "LAY corre sin privilegios: no puede controlar ventanas abiertas como administrador "
            "(Administrador de tareas, instaladores). Actívalo con 'Modo administrador'."
        )
    if carpetas == "1":
        avisos.append("Defender tiene 'Acceso controlado a carpetas': puede bloquear que LAY guarde en Documentos.")
    if camara == "Deny":
        avisos.append("Windows bloquea la cámara para apps de escritorio (Configuración > Privacidad > Cámara).")
    if micro == "Deny":
        avisos.append("Windows bloquea el micrófono para apps de escritorio (Configuración > Privacidad > Micrófono).")
    return {
        "windows": True,
        "es_admin": es_admin(),
        "uac_activo": uac[0] == "1" if uac and uac[0] else None,
        "acceso_controlado_carpetas": carpetas == "1",
        "camara_permitida": camara != "Deny",
        "microfono_permitido": micro != "Deny",
        "modo_admin_configurado": tarea,
        "avisos": avisos,
    }


def _exe() -> str:
    return sys.executable if getattr(sys, "frozen", False) else ""


def _elevado(script: str) -> dict:
    """Corre un script de PowerShell como administrador (Windows muestra UAC una vez)."""
    import ctypes

    r = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", "powershell.exe", f'-NoProfile -WindowStyle Hidden -Command "{script}"', None, 0
    )
    if r <= 32:
        return {"error": "No se aceptó el permiso de administrador (UAC)."}
    return {"ok": True}


def activar_modo_admin() -> dict:
    """Tarea programada: LAY arranca elevado al iniciar sesión, sin pedir UAC cada vez."""
    if not ES_WINDOWS:
        return {"error": "Solo en Windows."}
    exe = _exe()
    if not exe:
        return {"error": "Disponible en la versión instalada (LAY.exe)."}
    usuario = os.environ.get("USERNAME", "")
    script = (
        f"$a=New-ScheduledTaskAction -Execute '{exe}';"
        f"$t=New-ScheduledTaskTrigger -AtLogOn -User '{usuario}';"
        f"$p=New-ScheduledTaskPrincipal -UserId '{usuario}' -LogonType Interactive -RunLevel Highest;"
        "$s=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit 0;"
        f"Register-ScheduledTask -TaskName '{TAREA}' -Action $a -Trigger $t -Principal $p -Settings $s -Force"
    )
    return {**_elevado(script), "nota": "Desde el próximo inicio de sesión LAY arranca con permisos de administrador."}


def desactivar_modo_admin() -> dict:
    if not ES_WINDOWS:
        return {"error": "Solo en Windows."}
    return _elevado(f"Unregister-ScheduledTask -TaskName '{TAREA}' -Confirm:$false")


def reiniciar_como_admin() -> dict:
    """Abre ahora mismo una copia elevada de LAY (la actual se cierra sola al detectar la otra)."""
    import ctypes

    exe = _exe()
    if not ES_WINDOWS or not exe:
        return {"error": "Disponible en la versión instalada (LAY.exe)."}
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, "--relevo", None, 1)
    return {"ok": True} if r > 32 else {"error": "No se aceptó el permiso de administrador (UAC)."}
