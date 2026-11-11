"""Monitoreo del PC (lo que ya hace LAY hoy, pero expuesto como herramienta)."""

from __future__ import annotations

import psutil


def estado() -> dict:
    vm = psutil.virtual_memory()
    disco = psutil.disk_usage("C:\\" if psutil.WINDOWS else "/")
    bat = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None
    return {
        "cpu_pct": psutil.cpu_percent(interval=0.4),
        "ram_pct": vm.percent,
        "ram_libre_gb": round(vm.available / 1e9, 1),
        "disco_pct": disco.percent,
        "disco_libre_gb": round(disco.free / 1e9, 1),
        "bateria_pct": bat.percent if bat else None,
        "cargando": bat.power_plugged if bat else None,
    }


def procesos_top(n: int = 8, por: str = "memoria") -> list[dict]:
    procs = []
    for p in psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]):
        try:
            procs.append(
                {
                    "pid": p.info["pid"],
                    "nombre": p.info["name"],
                    "ram_mb": round(p.info["memory_info"].rss / 1e6),
                    "cpu": p.info["cpu_percent"],
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied, TypeError):
            continue
    clave = "ram_mb" if por == "memoria" else "cpu"
    return sorted(procs, key=lambda x: x[clave] or 0, reverse=True)[:n]
