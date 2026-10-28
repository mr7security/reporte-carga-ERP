#!/usr/bin/env python3
"""
Registro de reportes disponibles en el dashboard y en el envío diario.
Añadir un reporte nuevo = añadir un módulo con fetch_data()/build_html() y
registrarlo aquí. El resto (dashboard, config por reporte, cron) ya es genérico.
"""
import report_core as _carga   # "Previsión de Carga"
import ventas as _ventas       # "Ventas (Alb)"

REPORTS = [
    {"id": "carga",  "name": "Previsión de Carga", "subject": "Previsión de Carga",
     "fetch": _carga.fetch_data,  "build": _carga.build_html},
    {"id": "ventas", "name": "Ventas (Alb)",       "subject": "Ventas (Alb)",
     "fetch": _ventas.fetch_data, "build": _ventas.build_html},
]

_BYID = {r["id"]: r for r in REPORTS}


def get(rid):
    return _BYID.get(rid)


def ids():
    return [r["id"] for r in REPORTS]
