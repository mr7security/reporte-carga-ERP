#!/usr/bin/env python3
"""
Núcleo reutilizable del reporte "Previsión de Carga" (ERP ATENEA2 / BBDD GRUPO).
Lo usan: el dashboard (app.py, visor en vivo) y el envío diario (send_daily.py).
No envía nada por sí mismo; expone funciones:
  - fetch_data()            -> dict con los 5 datasets
  - build_html(data, full)  -> HTML (completo para email / fragmento para dashboard)
  - send_email(html, recipients, subject)
"""
import os
import smtplib
import datetime as dt
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import queries as Q

# ---------------------------------------------------------------------------
# Config desde entorno
# ---------------------------------------------------------------------------
def env(name, default=None, required=False):
    v = os.environ.get(name, default)
    if required and (v is None or v == ""):
        raise RuntimeError(f"Falta la variable de entorno obligatoria: {name}")
    return v

def db_cfg():
    return dict(
        server=env("DB_SERVER", required=True),
        port=env("DB_PORT", "1433"),
        user=env("DB_USER", required=True),
        password=env("DB_PASSWORD", required=True),
        database=env("DB_NAME", "GRUPO"),
        tds_version=env("DB_TDS_VERSION", "7.4"),
    )

# ---------------------------------------------------------------------------
# Mapeo de columnas (según el layout real del ERP)
# ---------------------------------------------------------------------------
LABELS = {
    "STN":"STN", "ALA":"Alaplana", "KER":"Keratile", "VIT":"Vitacer",
    "VNX":"Venux", "CLO":"C.Logístico", "CL2":"C.Logístico 2",
    "CL3":"C.Logístico 3", "CL8":"C.Logístico 8", "NAV":"Nave",
}
# Carga actual (Cargado / En proceso): SIN Venux; NAV se pliega a STN
CARGA_COLS = [(c, LABELS[c]) for c in ("STN","ALA","KER","VIT","CLO","CL2","CL3","CL8")]
# Stock Actual (Producto / Almacén): CON Venux y columna Nave (NAV separado)
STOCK_COLS = [(c, LABELS[c]) for c in ("STN","ALA","KER","VIT","VNX","CLO","CL2","CL3","CL8","NAV")]

CODE_MAP = {
    "ST":"STN","AL":"ALA","KE":"KER","VI":"VIT","CL":"CLO","C2":"CL2","C3":"CL3","C8":"CL8",
    "STN":"STN","S":"STN","NAV":"NAV","VIT":"VIT","W":"VIT","VNX":"VNX",
    "CLO":"CLO","C":"CLO","CL2":"CL2","2":"CL2","CL3":"CL3","3":"CL3","CL8":"CL8","8":"CL8",
    "ALA":"ALA","KER":"KER",
}
def canon(code):
    return CODE_MAP.get(str(code).strip(), str(code).strip())

# ---------------------------------------------------------------------------
# Formato es-ES
# ---------------------------------------------------------------------------
def fnum(v, dec=0):
    if v is None: v = 0
    try: v = float(v)
    except (TypeError, ValueError): return str(v)
    s = f"{v:,.{dec}f}"
    return s.replace(",", "·").replace(".", ",").replace("·", ".")
def fm2(v): return fnum(v, 2)
def fpz(v): return fnum(v, 0)

# ---------------------------------------------------------------------------
# Acceso a datos
# ---------------------------------------------------------------------------
def fetch_data():
    """Ejecuta las 5 consultas y devuelve dict con listas de dicts."""
    import pymssql
    c = db_cfg()
    cn = pymssql.connect(server=c["server"], port=str(c["port"]), user=c["user"],
                         password=c["password"], database=c["database"],
                         tds_version=c["tds_version"], login_timeout=30, timeout=90)
    cur = cn.cursor(as_dict=True)
    def run_last(sql):
        cur.execute(sql); data=[]
        while True:
            if cur.description is not None:
                try: data = cur.fetchall()
                except Exception: data = []
            if not cur.nextset(): break
        return data
    try:
        data = {
            "GRID":       run_last(Q.GRID_PRINCIPAL),
            "CARGADO":    run_last(Q.CARGADO),
            "EN_PROCESO": run_last(Q.EN_PROCESO),
            "PRODUCTO":   run_last(Q.PRODUCTO),
            "ALMACEN":    run_last(Q.ALMACEN),
        }
    finally:
        cn.close()
    return data

# ---------------------------------------------------------------------------
# Render HTML (tablas con estilos inline: válido para email y para el visor)
# ---------------------------------------------------------------------------
GREEN="#4a9e4a"; RED="#b0484a"; BORDER="#c8c8c8"; HEAD_TXT="#ffffff"
ROW_A="#fbfbe8"; ROW_B="#ffffff"

def th(txt, bg, color=HEAD_TXT, span=1, align="center"):
    return (f'<th colspan="{span}" style="background:{bg};color:{color};border:1px solid {BORDER};'
            f'padding:4px 8px;font:bold 12px Segoe UI,Arial;text-align:{align};">{txt}</th>')
def td(txt, bg=ROW_B, align="right", bold=False):
    w = "bold" if bold else "normal"
    return (f'<td style="background:{bg};color:#1f2937;border:1px solid {BORDER};padding:3px 8px;'
            f'font:{w} 12px Segoe UI,Arial;text-align:{align};white-space:nowrap;">{txt}</td>')

def _grid(data):
    prep = [("M2P","M2",fm2),("PzP","Pz",fpz),("UdP","Ud",fpz),("PcP","PC",fpz),
            ("PiP","Pi",fpz),("PzP1","Pz",fpz),("MuP","Mu",fpz)]
    tot  = [("M2T","M2",fm2),("PzT","Pz",fpz),("UdT","Ud",fpz),("PcT","PC",fpz),
            ("PiT","Pi",fpz),("PzT1","Pz",fpz),("MuT","Mu",fpz)]
    h  = '<table style="border-collapse:collapse;margin-bottom:18px;">'
    h += "<tr>" + th("Fecha", GREEN) + th("Preparado", GREEN, span=len(prep)) + th("Total", RED, span=len(tot)) + "</tr>"
    h += "<tr>" + th("", GREEN)
    for _,lbl,_ in prep: h += th(lbl, GREEN)
    for _,lbl,_ in tot:  h += th(lbl, RED)
    h += "</tr>"
    for i,r in enumerate(data):
        bg = ROW_A if i%2==0 else ROW_B
        f = r.get("Fecha")
        fstr = f.strftime("%d/%m/%Y") if isinstance(f,(dt.date,dt.datetime)) else (str(f)[:10] if f else "")
        h += "<tr>" + td(fstr, bg, align="center", bold=True)
        for key,_,fmt in prep: h += td(fmt(r.get(key)), bg)
        for key,_,fmt in tot:  h += td(fmt(r.get(key)), bg)
        h += "</tr>"
    return h + "</table>"

def _panel(titulo, filas, cols):
    h  = '<table style="border-collapse:collapse;margin-bottom:14px;">'
    h += "<tr>" + th(titulo, "#3a6ea5") + th("", "#3a6ea5")
    for _,lbl in cols: h += th(lbl, "#3a6ea5")
    h += th("Total", "#2a4a6a") + "</tr>"
    for etiqueta, porcentro in filas:
        for unidad, fmt, key in (("M2", fm2, "m2"), ("Pz", fpz, "pz")):
            h += "<tr>" + td(etiqueta if unidad=="M2" else "", "#eef3f8", align="left", bold=True)
            h += td(unidad, "#eef3f8", align="left")
            total = 0
            for cod,_ in cols:
                val = porcentro.get(cod, {}).get(key, 0) or 0
                total += val
                h += td(fmt(val))
            h += td(fmt(total), "#eef3f8", bold=True) + "</tr>"
    return h + "</table>"

def _por_centro(rows, fold_nav=False):
    d = {}
    for r in rows:
        cod = canon(r.get("centro") if r.get("centro") is not None else r.get("almacen"))
        if fold_nav and cod == "NAV": cod = "STN"
        d.setdefault(cod, {"m2":0,"pz":0})
        d[cod]["m2"] += float(r.get("metros") or 0)
        d[cod]["pz"] += float(r.get("piezas") or 0)
    return d

def _tables(data, datos_act):
    grid = _grid(data["GRID"])
    carga = _panel("Carga actual", [
        ("Cargado",   _por_centro(data["CARGADO"],   fold_nav=True)),
        ("En proceso",_por_centro(data["EN_PROCESO"],fold_nav=True)),
    ], CARGA_COLS)
    # Producto
    prod_by_unit = {r.get("UD"): r for r in data["PRODUCTO"]}
    PROD_KEYS = {"STN":"STN","ALA":"ALA","KER":"KER","VIT":"VIT","VNX":"VNX"}
    hp  = '<table style="border-collapse:collapse;margin-bottom:14px;">'
    hp += "<tr>" + th("Stock Actual", "#8a6d3b") + th("", "#8a6d3b")
    for _,lbl in STOCK_COLS: hp += th(lbl, "#8a6d3b")
    hp += th("Total", "#5a4420") + "</tr>"
    for unidad, fmt in (("M2", fm2), ("PZ", fpz)):
        r = prod_by_unit.get(unidad, {})
        hp += "<tr>" + td("Producto" if unidad=="M2" else "", "#f6efe0", align="left", bold=True)
        hp += td("M2" if unidad=="M2" else "Pz", "#f6efe0", align="left")
        total = 0
        for cod,_ in STOCK_COLS:
            if cod in PROD_KEYS:
                val = float(r.get(PROD_KEYS[cod]) or 0); total += val
                hp += td(fmt(val))
            else:
                hp += td("", "#f0f0f0")
        hp += td(fmt(total), "#f6efe0", bold=True) + "</tr>"
    hp += "</table>"
    # Almacén
    alm = {}
    for r in data["ALMACEN"]:
        cod = canon(r.get("situacionerp")); u = r.get("atrUnidad"); t = float(r.get("tot") or 0)
        alm.setdefault(cod, {"M2":0,"PZ":0})
        if u in ("M2","PZ"): alm[cod][u] += t
    ha  = '<table style="border-collapse:collapse;margin-bottom:14px;">'
    ha += "<tr>" + th(f"Almacén — datos act.: {datos_act}", "#8a6d3b", span=2+len(STOCK_COLS)+1) + "</tr>"
    ha += "<tr>" + th("", "#8a6d3b") + th("", "#8a6d3b")
    for _,lbl in STOCK_COLS: ha += th(lbl, "#8a6d3b")
    ha += th("Total", "#5a4420") + "</tr>"
    for unidad, fmt in (("M2", fm2), ("PZ", fpz)):
        ha += "<tr>" + td("", "#f6efe0") + td("M2" if unidad=="M2" else "Pz", "#f6efe0", align="left")
        total = 0
        for cod,_ in STOCK_COLS:
            val = alm.get(cod, {}).get(unidad, 0); total += val
            ha += td(fmt(val))
        ha += td(fmt(total), "#f6efe0", bold=True) + "</tr>"
    ha += "</table>"
    return grid + carga + hp + ha

def _logo_src():
    """Logo de static/ incrustado como data URI (para que se vea también en el correo)."""
    import glob, base64, mimetypes
    base = os.path.dirname(os.path.abspath(__file__))
    for ext in ("png", "svg", "jpg", "jpeg", "webp"):
        hits = glob.glob(os.path.join(base, "static", f"logo.{ext}"))
        if hits:
            mime = mimetypes.guess_type(hits[0])[0] or "image/png"
            with open(hits[0], "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            return f"data:{mime};base64,{b64}"
    return ""

def build_html(data, full=True, datos_act=None):
    """full=True -> documento completo (email). full=False -> fragmento (dashboard)."""
    if datos_act is None:
        datos_act = dt.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    tables = _tables(data, datos_act)
    now = dt.datetime.now()
    DIAS = ["Lunes","Martes","Miércoles","Jueves","Viernes","Sábado","Domingo"]
    MESES = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto",
             "septiembre","octubre","noviembre","diciembre"]
    fecha_larga = (f"{DIAS[now.weekday()]}, {now.day} de {MESES[now.month-1]} "
                   f"de {now.year}, {now.strftime('%H:%M:%S')}")
    dash_url = env("DASHBOARD_URL", "http://10.50.69.121:8070")

    logo = _logo_src()
    logo_cell = (f'<img src="{logo}" alt="SGP" style="height:42px;background:#fff;border-radius:6px;padding:3px 7px">'
                 if logo else '<span style="font:bold 20px Segoe UI,Arial;color:#2a4a6a">SGP</span>')
    # Cabecera: logo izquierda · título centro · fecha/hora derecha (tabla, robusta en email)
    header = (
        '<table style="width:100%;border-collapse:collapse;margin-bottom:18px;"><tr>'
        f'<td style="width:30%;text-align:left;vertical-align:middle;">{logo_cell}</td>'
        '<td style="width:40%;text-align:center;vertical-align:middle;">'
        '<span style="font:bold 20px Segoe UI,Arial;color:#2a4a6a;text-transform:uppercase;letter-spacing:.04em;">Previsión de Carga</span></td>'
        '<td style="width:30%;text-align:right;vertical-align:middle;font:12px Segoe UI,Arial;color:#777;">'
        f'Generado<br><b style="color:#444;">{fecha_larga}</b></td>'
        '</tr></table>'
    )
    footer = (
        '<p style="text-align:center;font:bold 11px Segoe UI,Arial;color:#8a8a8a;'
        'letter-spacing:.12em;text-transform:uppercase;margin:20px 0 4px;">SGP — Departamento de IT</p>'
        '<p style="text-align:center;font:12px Segoe UI,Arial;color:#777;margin:0;">'
        f'Para modificar las reglas de envío, <a href="{dash_url}" style="color:#3b82f6;text-decoration:none;font-weight:600;">pulse aquí</a>.</p>'
    )
    inner = f'{header}{tables}{footer}'
    if not full:
        return inner
    return (f'<!doctype html><html><body style="margin:0;padding:16px;background:#f0f0f0;">'
            f'<div style="max-width:1150px;margin:auto;background:#fff;padding:18px 20px;border:1px solid {BORDER};">'
            f'{inner}'
            f'</div></body></html>')

# ---------------------------------------------------------------------------
# Envío
# ---------------------------------------------------------------------------
def send_email(html, recipients, subject):
    if isinstance(recipients, str):
        recipients = [recipients]
    recipients = [r.strip() for r in recipients if r and r.strip()]
    if not recipients:
        raise RuntimeError("Sin destinatarios activos.")
    host = env("SMTP_HOST", required=True); port = int(env("SMTP_PORT", "587"))
    tls  = env("SMTP_TLS", "starttls"); user = env("SMTP_USER", ""); pw = env("SMTP_PASS", "")
    mail_from = env("MAIL_FROM", required=True)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{subject} — {dt.datetime.now().strftime('%d/%m/%Y')}"
    msg["From"] = mail_from
    msg["To"] = ", ".join(recipients)
    msg.attach(MIMEText("Abre este correo en un cliente compatible con HTML.", "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    if tls == "ssl":
        srv = smtplib.SMTP_SSL(host, port, timeout=30)
    else:
        srv = smtplib.SMTP(host, port, timeout=30)
        if tls == "starttls": srv.starttls()
    if user: srv.login(user, pw)
    srv.sendmail(mail_from, recipients, msg.as_string())
    srv.quit()
    return recipients
