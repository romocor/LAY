"""LAY PC — servidor MCP.

Expone el PC de Robert a Claude (Desktop, Code o la propia app LAY).

  Local (Claude Desktop / Claude Code):  python -m lay_mcp.server
  Remoto (HTTP con token):               python -m lay_mcp.server --http --port 8766

Cada herramienta "sensible" exige confirmar=true. Sin eso devuelve una
solicitud de confirmación: el cliente debe preguntarle a Robert primero.
"""

from __future__ import annotations

import argparse
import os

from mcp.server.fastmcp import FastMCP

from lay_core import archivos, blackboard, bus, correo, escritorio, sistema

mcp = FastMCP(
    "lay-pc",
    instructions=(
        "Eres el puente de LAY con el PC de Robert (Windows 11, multi-monitor). "
        "Lee y busca libremente. Para escribir texto, cerrar ventanas o enviar correos "
        "primero llama sin confirmar, muestra el resumen a Robert y solo repite con "
        "confirmar=true si dice que sí. Nunca borres archivos."
    ),
)


# ---------- Sistema ----------
@mcp.tool()
def sistema_estado() -> dict:
    """CPU, RAM, disco y batería del PC."""
    return sistema.estado()


@mcp.tool()
def sistema_procesos(n: int = 8, por: str = "memoria") -> list[dict]:
    """Procesos que más consumen. por = 'memoria' | 'cpu'."""
    return sistema.procesos_top(n, por)


# ---------- Archivos ----------
@mcp.tool()
def archivos_buscar(
    consulta: str,
    carpeta: str | None = None,
    extension: str | None = None,
    limite: int = 30,
    solo_carpetas: bool = False,
) -> list[dict]:
    """Busca archivos o carpetas por nombre en el PC (Everything si está instalado)."""
    return archivos.buscar(consulta, carpeta, extension, limite, solo_carpetas)


@mcp.tool()
def archivos_listar(carpeta: str, limite: int = 100) -> list[dict]:
    """Lista el contenido de una carpeta."""
    return archivos.listar(carpeta, limite)


@mcp.tool()
def archivos_recientes(carpeta: str | None = None, dias: int = 7) -> list[dict]:
    """Archivos modificados en los últimos N días (por defecto Descargas)."""
    return archivos.recientes(carpeta, dias)


@mcp.tool()
def archivos_abrir_por_nombre(consulta: str, extension: str | None = None) -> dict:
    """Busca un archivo o carpeta por nombre y abre la mejor coincidencia en un solo paso
    ("abre el presupuesto de Chancay"). Devuelve qué abrió y otras opciones si hubo varias."""
    mejor = archivos.mejor_coincidencia(consulta, extension)
    if mejor is None:
        return {"error": f"No encontré nada parecido a '{consulta}'"}
    return {**escritorio.abrir_seguro(mejor["ruta"]), "elegido": mejor}


@mcp.tool()
def abrir(ruta_o_url: str) -> dict:
    """Abre un archivo, carpeta o URL con la app predeterminada."""
    return escritorio.abrir_seguro(ruta_o_url)


# ---------- Ventanas / monitores ----------
@mcp.tool()
def monitores_listar() -> list[dict]:
    """Monitores conectados, ordenados de izquierda a derecha (1, 2, 3...)."""
    return escritorio.monitores()


@mcp.tool()
def ventanas_listar() -> list[dict]:
    """Ventanas abiertas con su posición."""
    return escritorio.ventanas()


@mcp.tool()
def ventana_mover(titulo: str, monitor: int = 1, posicion: str = "completa") -> dict:
    """Mueve una ventana a un monitor (1 = el de más a la izquierda) y posición: completa,
    maximizada, izquierda, derecha, arriba, abajo, arriba-izquierda, arriba-derecha,
    abajo-izquierda, abajo-derecha, centro."""
    return escritorio.mover_ventana(titulo, monitor, posicion)


@mcp.tool()
def ventana_enfocar(titulo: str) -> dict:
    """Trae una ventana al frente."""
    return escritorio.enfocar_ventana(titulo)


@mcp.tool()
def ventana_cerrar(titulo: str, confirmar: bool = False) -> dict:
    """[SENSIBLE] Cierra una ventana."""
    return escritorio.cerrar_ventana(titulo=titulo, confirmar=confirmar)


@mcp.tool()
def app_lanzar(nombre: str) -> dict:
    """Lanza una app por su alias (config/lay.json -> apps)."""
    return escritorio.lanzar_app(nombre)


@mcp.tool()
def workspace_aplicar(nombre: str) -> dict:
    """Abre un workspace: varias apps repartidas en los monitores (ej. 'trabajo', 'estudio')."""
    return escritorio.aplicar_workspace(nombre)


# ---------- Teclado / pantalla ----------
@mcp.tool()
def teclado_escribir(texto: str, ventana: str | None = None, confirmar: bool = False) -> dict:
    """[SENSIBLE] Escribe texto (con tildes/ñ) en la ventana indicada o la activa."""
    return escritorio.escribir(texto=texto, ventana=ventana, confirmar=confirmar)


@mcp.tool()
def teclado_atajo(teclas: str) -> dict:
    """Pulsa un atajo: 'ctrl+s', 'win+d', 'ctrl+shift+t'..."""
    return escritorio.atajo(teclas)


@mcp.tool()
def pantalla_capturar(monitor: int = 0) -> dict:
    """Captura de pantalla (0 = todos los monitores). Devuelve la ruta del PNG."""
    return escritorio.captura(monitor)


# ---------- Overlay holográfico ----------
@mcp.tool()
def overlay_mostrar_imagenes(
    rutas: list[str] | None = None, carpeta: str | None = None, consulta: str | None = None
) -> dict:
    """Muestra imágenes como tarjetas flotantes en el HUD de LAY, para manipularlas con las manos.
    Usa `consulta` con el nombre de una carpeta ("fotos obra Chancay") si no sabes la ruta;
    sin nada, muestra las más recientes de Imágenes."""
    if not rutas and not carpeta and consulta:
        encontradas = archivos.buscar(consulta, solo_carpetas=True, limite=5)
        con_fotos = [c for c in encontradas if archivos.imagenes(c["ruta"], limite=1)]
        if not con_fotos:
            return {"error": f"No encontré una carpeta con imágenes que se llame como '{consulta}'"}
        carpeta = con_fotos[0]["ruta"]
    rutas = rutas or archivos.imagenes(carpeta)
    if not rutas:
        return {"error": "No hay imágenes ahí"}
    r = bus.publicar("overlay.cargar", rutas=rutas)
    return {**r, "carpeta": carpeta, "imagenes": len(rutas)}


@mcp.tool()
def overlay_colocar(indice: int, x: float, y: float, escala: float = 1.0) -> dict:
    """Coloca la tarjeta N del overlay en (x, y) normalizados 0-1 con una escala."""
    return bus.publicar("overlay.colocar", indice=indice, x=x, y=y, escala=escala)


@mcp.tool()
def hud_decir(texto: str) -> dict:
    """Hace que LAY diga un texto en voz alta y lo muestre en el HUD."""
    return bus.publicar("voz.decir", texto=texto)


# ---------- Correo ----------
@mcp.tool()
def gmail_buscar(consulta: str = "is:unread", limite: int = 10) -> list[dict]:
    """Busca en Gmail con sintaxis de Gmail (is:unread, from:x, newer_than:2d...)."""
    return correo.gmail_buscar(consulta, limite)


@mcp.tool()
def gmail_borrador(para: str, asunto: str, cuerpo: str) -> dict:
    """Crea un borrador en Gmail (no envía)."""
    return correo.gmail_borrador(para, asunto, cuerpo)


@mcp.tool()
def gmail_enviar(para: str, asunto: str, cuerpo: str, confirmar: bool = False) -> dict:
    """[SENSIBLE] Envía un correo por Gmail."""
    return correo.gmail_enviar(para=para, asunto=asunto, cuerpo=cuerpo, confirmar=confirmar)


@mcp.tool()
def gmail_archivar(mensaje_id: str) -> dict:
    """Archiva un mensaje de Gmail (lo saca de la bandeja)."""
    return correo.gmail_archivar(mensaje_id)


@mcp.tool()
def outlook_no_leidos(limite: int = 10) -> list[dict]:
    """Correos no leídos de Outlook."""
    return correo.outlook_no_leidos(limite)


@mcp.tool()
def outlook_agenda(dias: int = 3) -> list[dict]:
    """Eventos del calendario de Outlook de los próximos N días."""
    return correo.outlook_agenda(dias)


@mcp.tool()
def outlook_enviar(para: str, asunto: str, cuerpo: str, confirmar: bool = False) -> dict:
    """[SENSIBLE] Envía un correo por Outlook."""
    return correo.outlook_enviar(para=para, asunto=asunto, cuerpo=cuerpo, confirmar=confirmar)


# ---------- Blackboard ----------
@mcp.tool()
def blackboard_pendientes(dias: int = 14) -> list[dict]:
    """Entregas y exámenes de Blackboard de los próximos N días (feed iCal)."""
    return blackboard.pendientes(dias)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--http", action="store_true", help="Servir por streamable HTTP (remoto)")
    ap.add_argument("--port", type=int, default=8766)
    a = ap.parse_args()
    if a.http:
        if not os.getenv("LAY_MCP_TOKEN"):
            raise SystemExit("Define LAY_MCP_TOKEN antes de exponer el MCP por red.")
        from remote.mcp_http import run_http

        run_http(mcp, a.port)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
