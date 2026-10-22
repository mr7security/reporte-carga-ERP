#!/usr/bin/env python3
"""
Dashboard "Previsión de Carga": visor en vivo del reporte + panel de control.
- Login con contraseña (APP_PASSWORD).
- Destinatarios editables, interruptor de envío on/off, hora y pausa-hasta.
La configuración se guarda en config.json; el envío diario (send_daily.py) la lee.
"""
import os, json, functools, datetime as dt
from flask import (Flask, request, session, redirect, url_for,
                   render_template_string, jsonify, abort)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except Exception:
    pass

import report_core as core

BASE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE, "config.json")

DEFAULT_CONFIG = {
    "enabled": True,
    "send_time": "07:30",
    "pause_until": None,          # "YYYY-MM-DD" o null
    "subject": "Previsión de Carga",
    "recipients": [],             # [{"email": "...", "active": true}]
}

def load_config():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg = json.load(f)
        for k, v in DEFAULT_CONFIG.items():
            cfg.setdefault(k, v)
        return cfg
    except Exception:
        return dict(DEFAULT_CONFIG)

def save_config(cfg):
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET", "cambia-esta-clave-secreta")
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")

def login_required(f):
    @functools.wraps(f)
    def wrap(*a, **k):
        if not session.get("auth"):
            return redirect(url_for("login"))
        return f(*a, **k)
    return wrap

# ---------------------------------------------------------------------------
LOGIN_HTML = """<!doctype html><html lang=es><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Acceso — Previsión de Carga</title>
<style>
:root{--bg:#0f172a;--card:#1e293b;--text:#e2e8f0;--muted:#94a3b8;--accent:#38bdf8;--alarm:#ef4444;}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);
display:flex;height:100vh;align-items:center;justify-content:center}
.card{background:var(--card);padding:34px;border-radius:16px;box-shadow:0 10px 40px rgba(0,0,0,.4);
width:340px;border-top:4px solid var(--accent)}
.brand{display:flex;align-items:center;gap:12px;margin-bottom:20px}
.brand img{height:38px;background:#fff;border-radius:8px;padding:3px 8px;display:none}
h1{font-size:1.05rem;font-weight:700;text-transform:uppercase;letter-spacing:.03em}
h1 span{color:var(--accent)}
input{width:100%;padding:11px;margin:6px 0;border:1px solid #334155;border-radius:8px;
font-size:14px;background:#0f1c30;color:var(--text)}
button{width:100%;padding:11px;background:var(--accent);color:#0f172a;border:0;border-radius:8px;
font-size:14px;font-weight:700;cursor:pointer;margin-top:10px;text-transform:uppercase;letter-spacing:.03em}
.err{color:var(--alarm);font-size:13px;margin-top:10px}</style></head><body>
<form class=card method=post>
<div class=brand><img src="/logo" alt="" onload="this.style.display='block'">
<h1>Previsión de <span>Carga</span></h1></div>
<input type=password name=password placeholder=Contraseña autofocus>
<button>Entrar</button>{% if error %}<div class=err>{{error}}</div>{% endif %}</form></body></html>"""

PAGE_HTML = """<!doctype html><html lang=es><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Previsión de Carga — SGP</title>
<style>
 :root{--bg:#0f172a;--card:#1e293b;--card2:#0f1c30;--text:#e2e8f0;--muted:#94a3b8;
   --ok:#22c55e;--alarm:#ef4444;--warn:#f59e0b;--accent:#38bdf8;}
 *{box-sizing:border-box;margin:0;padding:0}
 body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);padding:18px 22px}
 header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:16px}
 .hl{display:flex;align-items:center;gap:14px}
 #logo{height:42px;background:#fff;border-radius:8px;padding:3px 8px;display:none}
 h1{font-size:1.3rem;font-weight:600;text-transform:uppercase;letter-spacing:.03em}
 h1 span{color:var(--accent)}
 #reloj-box{text-align:right;line-height:1.2}
 #clock{font-size:.85rem;color:var(--text);font-variant-numeric:tabular-nums}
 #servidor{font-size:.72rem;color:var(--muted);margin-top:2px}
 #servidor:not(:empty)::before{content:"🖥 "}
 .hr{margin-left:auto;text-align:right}
 a.salir{display:inline-block;margin-top:5px;color:var(--muted);font-size:.72rem;text-decoration:none;text-transform:uppercase;letter-spacing:.03em}
 a.salir:hover{color:var(--accent)}
 .panel{background:var(--card);border-radius:16px;padding:16px 18px;margin-bottom:16px;border-top:4px solid var(--accent)}
 .panel h2{font-size:.95rem;margin:0 0 14px;text-transform:uppercase;letter-spacing:.03em;color:var(--accent)}
 .panel h2 .right{float:right}
 .row{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-end}
 .fld{display:flex;flex-direction:column;font-size:.72rem;gap:4px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}
 input,select{padding:9px;border:1px solid #334155;border-radius:8px;font-size:14px;background:var(--card2);color:var(--text)}
 .btn{padding:9px 15px;background:var(--card2);color:var(--text);border:1px solid #334155;border-radius:8px;
   cursor:pointer;font-size:.82rem;text-transform:uppercase;letter-spacing:.02em}
 .btn:hover{border-color:var(--accent)}
 .btn.alt{background:var(--accent);color:#0f172a;border-color:var(--accent);font-weight:700}
 .btn.warn{background:rgba(239,68,68,.15);color:#fca5a5;border-color:var(--alarm)}
 .switch{display:inline-flex;align-items:center;gap:8px;font-weight:600;font-size:.9rem}
 .switch input{width:16px;height:16px}
 table.rcp{width:100%;border-collapse:collapse;margin-top:10px}
 table.rcp td,table.rcp th{border-bottom:1px solid #24334a;padding:8px 6px;font-size:.82rem;text-align:left}
 table.rcp th{color:var(--muted);text-transform:uppercase;font-size:.66rem;letter-spacing:.04em}
 .muted{color:var(--muted);font-size:.75rem}
 .msg{font-size:.8rem;margin-left:10px;color:var(--accent)}
 /* el reporte va en tarjeta blanca (la tabla es clara, como el ERP) */
 .report{overflow:auto;background:#fff;color:#1f2937;border-radius:10px;padding:14px}
 footer{text-align:center;color:var(--muted);font-size:.72rem;letter-spacing:.14em;
   text-transform:uppercase;font-weight:700;margin-top:18px;padding-top:12px;border-top:1px solid #24334a}
 a{color:var(--accent)}
</style></head><body>
<header>
 <div class=hl>
  <img id=logo src="/logo" alt="" onload="this.style.display='block'">
  <h1>Previsión de <span>Carga</span></h1>
 </div>
 <div class=hr>
  <div id=reloj-box><div id=clock>--</div><div id=servidor>ERP ATENEA2 · GRUPO</div></div>
  <a class=salir href="{{url_for('logout')}}">Salir</a>
 </div>
</header>

 <div class=panel>
  <h2>Estado del envío</h2>
  <div class=row>
   <div class=switch>
     <label><input type=checkbox id=enabled {% if cfg.enabled %}checked{% endif %}> Envío diario activo</label>
   </div>
   <div class=fld><label>Hora de envío</label><input type=time id=send_time value="{{cfg.send_time}}"></div>
   <div class=fld><label>Pausar hasta (incluido)</label><input type=date id=pause_until value="{{cfg.pause_until or ''}}"></div>
   <div class=fld><label>Asunto</label><input type=text id=subject value="{{cfg.subject}}" size=26></div>
   <button class="btn alt" onclick=saveCfg()>Guardar</button>
   <span class=msg id=cfgmsg></span>
  </div>
  <p class=muted id=statusline style="margin-top:12px"></p>
 </div>

 <div class=panel>
  <h2>Destinatarios</h2>
  <div class=row>
   <div class=fld><label>Añadir correo</label><input type=email id=newmail placeholder="nombre@serviplana.es" size=28></div>
   <button class="btn alt" onclick=addMail()>Añadir</button>
   <button class="btn warn" onclick=sendNow()>Enviar ahora (prueba)</button>
   <span class=msg id=sendmsg></span>
  </div>
  <table class=rcp id=rcptbl></table>
 </div>

 <div class=panel>
  <h2>Reporte (vista en vivo) <button class="btn right" onclick=loadReport()>Actualizar</button></h2>
  <div class=report id=report><p class=muted>Cargando…</p></div>
 </div>

<footer>SGP — Departamento IT</footer>
<script>
const DIAS_SEM=["Domingo","Lunes","Martes","Miércoles","Jueves","Viernes","Sábado"];
const MESES_ES=["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"];
function fmtReloj(d){const p=n=>String(n).padStart(2,"0");
 return `${DIAS_SEM[d.getDay()]}, ${d.getDate()} de ${MESES_ES[d.getMonth()]} de ${d.getFullYear()}, ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;}
function tic(){document.getElementById('clock').textContent=fmtReloj(new Date());}
setInterval(tic,1000);tic();
let cfg = {{cfg_json|safe}};
function render(){
  const t=document.getElementById('rcptbl');
  let h="<tr><th>Correo</th><th>Activo</th><th></th></tr>";
  (cfg.recipients||[]).forEach((r,i)=>{
    h+=`<tr><td>${r.email}</td>
      <td><input type=checkbox ${r.active?'checked':''} onchange="toggle(${i})"></td>
      <td><a href="#" onclick="del(${i});return false" style="color:#b0484a">quitar</a></td></tr>`;
  });
  if(!(cfg.recipients||[]).length) h+="<tr><td colspan=3 class=muted>Sin destinatarios</td></tr>";
  t.innerHTML=h;
  statusLine();
}
function statusLine(){
  const s=document.getElementById('statusline');
  const act=(cfg.recipients||[]).filter(r=>r.active).length;
  let txt = cfg.enabled ? `Envío ACTIVO a las ${cfg.send_time} · ${act} destinatario(s) activo(s).` : "Envío DESACTIVADO.";
  if(cfg.pause_until) txt += ` En pausa hasta ${cfg.pause_until}.`;
  s.textContent=txt;
}
function collect(){
  cfg.enabled=document.getElementById('enabled').checked;
  cfg.send_time=document.getElementById('send_time').value;
  cfg.pause_until=document.getElementById('pause_until').value||null;
  cfg.subject=document.getElementById('subject').value;
}
async function post(cfg){
  const r=await fetch('api/config',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg)});
  return r.json();
}
async function saveCfg(){collect();const j=await post(cfg);cfg=j.config;render();flash('cfgmsg','Guardado ✓');}
async function addMail(){const e=document.getElementById('newmail').value.trim();if(!e)return;
  cfg.recipients=cfg.recipients||[];cfg.recipients.push({email:e,active:true});
  document.getElementById('newmail').value='';const j=await post(cfg);cfg=j.config;render();}
async function toggle(i){cfg.recipients[i].active=!cfg.recipients[i].active;const j=await post(cfg);cfg=j.config;render();}
async function del(i){cfg.recipients.splice(i,1);const j=await post(cfg);cfg=j.config;render();}
async function sendNow(){flash('sendmsg','Enviando…');
  const r=await fetch('api/send-now',{method:'POST'});const j=await r.json();
  flash('sendmsg', j.ok?('Enviado a: '+j.recipients.join(', ')):('Error: '+j.error));}
async function loadReport(){const d=document.getElementById('report');d.innerHTML='<p class=muted>Cargando…</p>';
  try{const r=await fetch('api/report');const t=await r.text();d.innerHTML=t;}catch(e){d.innerHTML='<p style="color:#b0484a">Error al cargar el reporte</p>';}}
function flash(id,txt){document.getElementById(id).textContent=txt;}
render();loadReport();
</script></body></html>"""

@app.route("/login", methods=["GET","POST"])
def login():
    error = None
    if request.method == "POST":
        if APP_PASSWORD and request.form.get("password") == APP_PASSWORD:
            session["auth"] = True
            return redirect(url_for("index"))
        error = "Contraseña incorrecta" if APP_PASSWORD else "APP_PASSWORD no configurada en el servidor"
    return render_template_string(LOGIN_HTML, error=error)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def index():
    cfg = load_config()
    return render_template_string(PAGE_HTML, cfg=cfg, cfg_json=json.dumps(cfg, ensure_ascii=False))

@app.route("/api/report")
@login_required
def api_report():
    try:
        data = core.fetch_data()
        return core.build_html(data, full=False)
    except Exception as e:
        return f'<p style="color:#b0484a">Error consultando el ERP: {e}</p>', 200

@app.route("/api/config", methods=["POST"])
@login_required
def api_config():
    incoming = request.get_json(force=True, silent=True) or {}
    cfg = load_config()
    for k in ("enabled","send_time","pause_until","subject","recipients"):
        if k in incoming:
            cfg[k] = incoming[k]
    # saneado mínimo de recipients
    clean = []
    for r in cfg.get("recipients", []):
        em = (r.get("email") or "").strip()
        if em and "@" in em:
            clean.append({"email": em, "active": bool(r.get("active", True))})
    cfg["recipients"] = clean
    save_config(cfg)
    return jsonify(ok=True, config=cfg)

@app.route("/api/send-now", methods=["POST"])
@login_required
def api_send_now():
    cfg = load_config()
    recipients = [r["email"] for r in cfg.get("recipients", []) if r.get("active")]
    try:
        data = core.fetch_data()
        html = core.build_html(data, full=True)
        sent = core.send_email(html, recipients, cfg.get("subject","Previsión de Carga"))
        return jsonify(ok=True, recipients=sent)
    except Exception as e:
        return jsonify(ok=False, error=str(e))

@app.route("/logo")
def logo():
    # Sirve el primer logo que encuentre en la carpeta static/ (png/svg/jpg).
    import glob
    from flask import send_file
    for ext in ("png", "svg", "jpg", "jpeg", "webp"):
        hits = glob.glob(os.path.join(BASE, "static", f"logo.{ext}"))
        if hits:
            return send_file(hits[0])
    abort(404)

@app.route("/healthz")
def healthz():
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("APP_PORT","8070")))
