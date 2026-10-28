#!/usr/bin/env python3
"""
Reporte 2 — "Ventas (Alb)".
Suma los totales del día (todo el grupo) de la tabla de análisis de ventas por
albaranes, replicando el informe "Ventas (Alb)" del ERP con "Incluir Ventas Hoy":

    SELECT SUM(Cantidad), SUM(ImporteLinea), SUM(DImporteLinea)
    FROM STN_ERP_ANALISIS_VENTAS_ALBARANES_TABLA
    WHERE CAST(Fecha AS date) = CAST(GETDATE() AS date)

Validado al céntimo contra el ERP (día cerrado 27/10/2026: 397.322,03 /
2.751.113,72 / 2.595.774,10). No filtra por Tipo ni por empresa.

Expone la misma interfaz que report_core: fetch_data() y build_html(data, full).
"""
import datetime as dt
import report_core as core
import reportlib

TABLA = "STN_ERP_ANALISIS_VENTAS_ALBARANES_TABLA"

SQL_TOTALES = f"""
SELECT COUNT(*)            AS n,
       SUM(Cantidad)       AS cant,
       SUM(ImporteLinea)   AS imp,
       SUM(DImporteLinea)  AS dimp
FROM {TABLA}
WHERE CAST(Fecha AS date) = CAST(GETDATE() AS date)
"""


# ---------------------------------------------------------------------------
# Acceso a datos (mismos reintentos que report_core para réplicas AlwaysOn)
# ---------------------------------------------------------------------------
def _fetch_once():
    import pymssql
    c = core.db_cfg()
    cn = pymssql.connect(server=c["server"], port=str(c["port"]), user=c["user"],
                         password=c["password"], database=c["database"],
                         tds_version=c["tds_version"], read_only=c["read_only"],
                         login_timeout=30, timeout=90)
    cur = cn.cursor(as_dict=True)
    try:
        try:
            cur.execute("SELECT GETDATE() AS now")
            srv = (cur.fetchall() or [{}])[0].get("now")
        except Exception:
            srv = None
        cur.execute(SQL_TOTALES)
        r = (cur.fetchall() or [{}])[0]
        return {
            "_server_time": srv,
            "n":    int(r.get("n") or 0),
            "cant": float(r.get("cant") or 0),
            "imp":  float(r.get("imp") or 0),
            "dimp": float(r.get("dimp") or 0),
        }
    finally:
        cn.close()


def fetch_data(intentos=4):
    import time
    last_err = None
    for i in range(intentos):
        try:
            return _fetch_once()
        except Exception as e:
            last_err = e
            m = str(e).lower()
            transitorio = ("3961" in m or "3960" in m or "snapshot" in m
                           or "deadlock" in m or "1205" in m)
            if transitorio and i < intentos - 1:
                time.sleep(2 + i * 2)
                continue
            raise
    raise last_err


# ---------------------------------------------------------------------------
# Render HTML (reutiliza estilos de report_core y el shell común)
# ---------------------------------------------------------------------------
def build_html(data, full=True):
    now = dt.datetime.now()
    srv = data.get("_server_time")
    fecha = (srv or now).strftime("%d/%m/%Y")
    datos_act = (srv.strftime("%d/%m/%Y %H:%M:%S") if srv
                 else now.strftime("%d/%m/%Y %H:%M:%S"))

    cant = core.fm2(data.get("cant"))
    imp = core.fm2(data.get("imp"))
    dimp = core.fm2(data.get("dimp"))
    n = data.get("n") or 0

    GREEN = core.GREEN
    # celda de total grande y en negrita
    def big(txt):
        return (f'<td style="background:#ffffff;color:#1f2937;border:1px solid {reportlib.BORDER};'
                f'padding:12px 10px;font:bold 20px Segoe UI,Arial;text-align:center;'
                f'white-space:nowrap;font-variant-numeric:tabular-nums;">{txt}</td>')

    body = (
        '<table width="100%" style="border-collapse:collapse;margin:0 auto 12px;width:100%;max-width:720px;">'
        + '<tr>' + core.th(f"Ventas del día &middot; {fecha}", GREEN, span=3) + '</tr>'
        + '<tr>'
        + core.th("Cantidad", GREEN)
        + core.th("ImporteLinea", GREEN)
        + core.th("DImporteLinea", GREEN)
        + '</tr>'
        + '<tr>' + big(cant) + big(imp) + big(dimp) + '</tr>'
        + '</table>'
        + f'<p style="text-align:center;font:12px Segoe UI,Arial;color:#777;margin:6px 0 0;">'
          f'Nº de líneas: {n} &middot; Datos actualizados: {datos_act}</p>'
    )

    dash_url = core.env("DASHBOARD_URL", "http://10.50.69.121:8070")
    return reportlib.document("Ventas (Alb)", body, full=full,
                              now=now, srv=srv, dash_url=dash_url)
