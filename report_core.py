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
        # read_only = ApplicationIntent=ReadOnly (necesario para réplicas secundarias AlwaysOn).
        # El reporte es de solo lectura, así que por defecto va activado.
        read_only=str(env("DB_READONLY", "true")).strip().lower() in ("1", "true", "yes", "si", "sí"),
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
def _fetch_once():
    import pymssql
    c = db_cfg()
    cn = pymssql.connect(server=c["server"], port=str(c["port"]), user=c["user"],
                         password=c["password"], database=c["database"],
                         tds_version=c["tds_version"], read_only=c["read_only"],
                         login_timeout=30, timeout=90)
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
        return {
            "GRID":       run_last(Q.GRID_PRINCIPAL),
            "CARGADO":    run_last(Q.CARGADO),
            "EN_PROCESO": run_last(Q.EN_PROCESO),
            "PRODUCTO":   run_last(Q.PRODUCTO),
            "ALMACEN":    run_last(Q.ALMACEN),
        }
    finally:
        cn.close()

def fetch_data(intentos=4):
    """Ejecuta las 5 consultas con reintentos.
    Las réplicas secundarias AlwaysOn corren bajo snapshot isolation y pueden fallar
    de forma transitoria (errores 3960/3961) si hay un cambio de metadatos (DDL) a la vez.
    Reintentar con una nueva transacción (snapshot fresco) lo resuelve."""
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
                time.sleep(2 + i * 2)   # backoff: 2s, 4s, 6s
                continue
            raise
    raise last_err

# ---------------------------------------------------------------------------
# Render HTML (tablas con estilos inline: válido para email y para el visor)
# ---------------------------------------------------------------------------
GREEN="#4a9e4a"; RED="#b0484a"; BORDER="#c8c8c8"; HEAD_TXT="#ffffff"
ROW_A="#fbfbe8"; ROW_B="#ffffff"

def th(txt, bg, color=HEAD_TXT, span=1, align="center"):
    return (f'<th colspan="{span}" style="background:{bg};color:{color};border:1px solid {BORDER};'
            f'padding:3px 6px;font:bold 11px Segoe UI,Arial;text-align:{align};">{txt}</th>')
def td(txt, bg=ROW_B, align="center", bold=False, rowspan=1):
    w = "bold" if bold else "normal"
    rs = f' rowspan="{rowspan}"' if rowspan != 1 else ''
    return (f'<td{rs} style="background:{bg};color:#1f2937;border:1px solid {BORDER};padding:2px 6px;'
            f'font:{w} 11px Segoe UI,Arial;text-align:{align};vertical-align:middle;white-space:nowrap;">{txt}</td>')

def _grid(data):
    prep = [("M2P","M2",fm2),("PzP","Pz",fpz),("UdP","Ud",fpz),("PcP","PC",fpz),
            ("PiP","Pi",fpz),("PzP1","Pz",fpz),("MuP","Mu",fpz)]
    tot  = [("M2T","M2",fm2),("PzT","Pz",fpz),("UdT","Ud",fpz),("PcT","PC",fpz),
            ("PiT","Pi",fpz),("PzT1","Pz",fpz),("MuT","Mu",fpz)]
    h  = '<table width="100%" style="border-collapse:collapse;margin-bottom:18px;width:100%;">'
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

# Anchos de columna idénticos para las 3 tablas de abajo (así STN queda bajo STN, etc.)
# 2 columnas de etiqueta + N columnas de datos + Total. table-layout:fixed las respeta en Outlook.
def _colgroup():
    n = len(STOCK_COLS)
    w = round(84.0 / (n + 1), 3)   # datos + total reparten el 84%
    cols = '<col style="width:11%"><col style="width:5%">'
    cols += ('<col style="width:%s%%">' % w) * (n + 1)
    return "<colgroup>" + cols + "</colgroup>"

_BOTTOM_TBL = ('<table width="100%" style="border-collapse:collapse;margin-bottom:14px;'
               'width:100%;table-layout:fixed;">')

def _por_centro(rows, drop_nav=False):
    d = {}
    for r in rows:
        cod = canon(r.get("centro") if r.get("centro") is not None else r.get("almacen"))
        # En Cargado/En proceso, 'NAV' es un DUPLICADO de 'STN' (mismas órdenes bajo
        # otro código por el UNION de la consulta): se descarta para no duplicar STN.
        if drop_nav and cod == "NAV":
            continue
        d.setdefault(cod, {"m2":0,"pz":0})
        d[cod]["m2"] += float(r.get("metros") or 0)
        d[cod]["pz"] += float(r.get("piezas") or 0)
    return d

def _tables(data, datos_act):
    grid = _grid(data["GRID"])
    cols = STOCK_COLS
    # --- datos agregados ---
    c_carg = _por_centro(data["CARGADO"],    drop_nav=True)
    c_proc = _por_centro(data["EN_PROCESO"], drop_nav=True)
    prod   = {r.get("UD"): r for r in data["PRODUCTO"]}
    PROD_KEYS = {"STN":"STN","ALA":"ALA","KER":"KER","VIT":"VIT","VNX":"VNX"}
    alm = {}
    for r in data["ALMACEN"]:
        c = canon(r.get("situacionerp")); u = r.get("atrUnidad"); t = float(r.get("tot") or 0)
        alm.setdefault(c, {"M2":0,"PZ":0})
        if u in ("M2","PZ"): alm[c][u] += t

    AZ1, AZ2 = "#3a6ea5", "#2a4a6a"   # azul (Carga actual)
    MA1, MA2 = "#8a6d3b", "#5a4420"   # marrón (Stock / Almacén)
    LB, LN   = "#eef3f8", "#f6efe0"   # fondos de etiqueta

    # UNA sola tabla para las 3 secciones -> columnas alineadas en CUALQUIER cliente,
    # incluido Outlook Classic (motor Word), que ignora table-layout:fixed / colgroup.
    h = ('<table width="100%" style="border-collapse:collapse;margin-bottom:14px;'
         'width:100%;table-layout:fixed;">' + _colgroup())

    def band(title, bg, bg2):
        r = "<tr>" + th(title, bg, span=2)
        for _, lbl in cols: r += th(lbl, bg)
        return r + th("Total", bg2) + "</tr>"

    def fullband(title, bg):
        return "<tr>" + th(title, bg, span=2 + len(cols) + 1) + "</tr>"

    def filas(label, lblbg, valfn):
        out = ""
        for i, (disp, fmt, key) in enumerate((("M2", fm2, "M2"), ("Pz", fpz, "PZ"))):
            out += "<tr>"
            if i == 0:
                out += td(label, lblbg, bold=True, rowspan=2)
            out += td(disp, lblbg)
            total = 0.0
            for cod, _ in cols:
                v = valfn(cod, key)
                if v is None:
                    out += td("", "#f0f0f0")     # C.Logístico sin dato en Producto
                else:
                    total += v
                    out += td(fmt(v))
            out += td(fmt(total), lblbg, bold=True) + "</tr>"
        return out

    cargfn = lambda cod, key: c_carg.get(cod, {}).get("m2" if key == "M2" else "pz", 0)
    procfn = lambda cod, key: c_proc.get(cod, {}).get("m2" if key == "M2" else "pz", 0)
    almfn  = lambda cod, key: alm.get(cod, {}).get(key, 0)
    def prodfn(cod, key):
        if cod in PROD_KEYS:
            return float((prod.get(key, {}) or {}).get(PROD_KEYS[cod]) or 0)
        return None

    h += band("Carga actual", AZ1, AZ2)
    h += filas("Cargado",    LB, cargfn)
    h += filas("En proceso", LB, procfn)
    h += band("Stock Actual", MA1, MA2)
    h += filas("Producto", LN, prodfn)
    h += fullband(f"Almacén — datos act.: {datos_act}", MA2)
    h += filas("Almacén", LN, almfn)
    h += "</table>"
    return grid + h

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

    # Cabecera SIN logo: título centrado · fecha/hora a la derecha (tabla al 100%, robusta en Outlook)
    header = (
        '<table width="100%" style="width:100%;border-collapse:collapse;margin-bottom:16px;"><tr>'
        '<td style="width:30%;">&nbsp;</td>'
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
    return (f'<!doctype html><html><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"></head>'
            f'<body style="margin:0;padding:12px;background:#f0f0f0;">'
            f'<div style="max-width:1150px;width:100%;margin:auto;background:#fff;padding:16px;border:1px solid {BORDER};">'
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
