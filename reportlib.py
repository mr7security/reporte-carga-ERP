#!/usr/bin/env python3
"""
Shell común de los reportes HTML: cabecera, pie y envoltura del documento.
Lo usan report_core (Previsión de Carga) y ventas (Ventas Alb) para que todos
los reportes compartan la misma cabecera/pie y se vean igual en correo y visor.
"""
import datetime as dt

BORDER = "#c8c8c8"
DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


def largo(d):
    """Fecha/hora larga en español: 'Martes, 28 de octubre de 2026, 11:30:00'."""
    return f"{DIAS[d.weekday()]}, {d.day} de {MESES[d.month-1]} de {d.year}, {d.strftime('%H:%M:%S')}"


def header(title, now, srv):
    """Cabecera: título centrado y, a la derecha, hora de generación + hora del servidor de datos."""
    fecha_larga = largo(now)
    srv_largo = largo(srv) if srv else "no disponible"
    return (
        '<table width="100%" style="width:100%;border-collapse:collapse;margin-bottom:16px;"><tr>'
        '<td style="width:28%;">&nbsp;</td>'
        '<td style="width:38%;text-align:center;vertical-align:middle;">'
        f'<span style="font:bold 20px Segoe UI,Arial;color:#2a4a6a;text-transform:uppercase;letter-spacing:.04em;">{title}</span></td>'
        '<td style="width:34%;text-align:right;vertical-align:middle;font:11px Segoe UI,Arial;color:#777;">'
        f'Reporte generado<br><b style="color:#444;">{fecha_larga}</b>'
        f'<br><span style="color:#999;">Datos del servidor</span><br><b style="color:#444;">{srv_largo}</b></td>'
        '</tr></table>'
    )


def footer(dash_url):
    return (
        '<p style="text-align:center;font:bold 11px Segoe UI,Arial;color:#8a8a8a;'
        'letter-spacing:.12em;text-transform:uppercase;margin:20px 0 4px;">SGP — Departamento de IT</p>'
        '<p style="text-align:center;font:12px Segoe UI,Arial;color:#777;margin:0;">'
        f'Para modificar las reglas de envío, <a href="{dash_url}" style="color:#3b82f6;text-decoration:none;font-weight:600;">pulse aquí</a>.</p>'
    )


def document(title, body, *, full=True, now=None, srv=None, dash_url="http://10.50.69.121:8070"):
    """Compone el documento: cabecera + cuerpo + pie.
    full=True -> HTML completo (email). full=False -> fragmento (visor del dashboard)."""
    now = now or dt.datetime.now()
    inner = f'{header(title, now, srv)}{body}{footer(dash_url)}'
    if not full:
        return inner
    return (f'<!doctype html><html><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
            f'<body style="margin:0;padding:12px;background:#f0f0f0;">'
            f'<div style="max-width:1150px;width:100%;margin:auto;background:#fff;padding:16px;border:1px solid {BORDER};">'
            f'{inner}'
            f'</div></body></html>')
