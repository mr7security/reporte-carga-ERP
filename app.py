#!/usr/bin/env python3
"""
Dashboard de reportes del ERP (SGP): un visor en vivo + panel de control por
cada reporte, en pestañas independientes.
- Login con contraseña (APP_PASSWORD).
- Cada reporte tiene su interruptor on/off, sus horas de envío, su pausa, su
  asunto y su lista de destinatarios (config.<id>.json, vía configstore).
El envío diario (send_daily.py) lee esas mismas configuraciones.
"""
import os, json, functools, re

from flask import (Flask, request, session, redirect, url_for,
                   render_template_string, jsonify, abort)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except Exception:
    pass

import reports as R
import configstore as CS

BASE = os.path.dirname(os.path.abspath(__file__))

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


def _clean_config(incoming, rid):
    """Normaliza una config entrante: horas HH:MM únicas/ordenadas y destinatarios sin duplicados."""
    cfg = CS.load_config(rid)
    for k in ("enabled", "send_times", "pause_until", "subject", "recipients", "weekdays_only"):
        if k in incoming:
            cfg[k] = incoming[k]
    cfg["weekdays_only"] = bool(cfg.get("weekdays_only", True))
    horas = []
    for t in cfg.get("send_times", []):
        t = (t or "").strip()
        if re.match(r"^\d{2}:\d{2}$", t) and t not in horas:
            horas.append(t)
    cfg["send_times"] = sorted(horas)
    cfg.pop("send_time", None)
    clean, seen = [], set()
    for r in cfg.get("recipients", []):
        em = (r.get("email") or "").strip()
        key = em.lower()
        if em and "@" in em and key not in seen:
            seen.add(key)
            clean.append({"email": em, "active": bool(r.get("active", True))})
    cfg["recipients"] = clean
    return cfg


# ---------------------------------------------------------------------------
LOGIN_HTML = """<!doctype html><html lang=es><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Acceso — Reportes SGP</title>
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
<h1>Reportes <span>SGP</span></h1></div>
<input type=password name=password placeholder=Contraseña autofocus>
<button>Entrar</button>{% if error %}<div class=err>{{error}}</div>{% endif %}</form></body></html>"""

PAGE_HTML = """<!doctype html><html lang=es><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Reportes — SGP</title>
<style>
 :root{--bg:#0f172a;--card:#1e293b;--card2:#0f1c30;--text:#e2e8f0;--muted:#94a3b8;
   --ok:#22c55e;--alarm:#ef4444;--warn:#f59e0b;--accent:#38bdf8;}
 *{box-sizing:border-box;margin:0;padding:0}
 body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--text);padding:18px 22px}
 header{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;margin-bottom:14px}
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
 /* pestañas */
 .tabs{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px;border-bottom:1px solid #24334a;padding-bottom:0}
 .tab{background:transparent;color:var(--muted);border:0;border-bottom:3px solid transparent;
   padding:10px 18px;font-size:.9rem;font-weight:600;cursor:pointer;text-transform:uppercase;letter-spacing:.02em}
 .tab:hover{color:var(--text)}
 .tab.on{color:var(--accent);border-bottom-color:var(--accent)}
 :root{--ctl-h:42px}
 .panel{background:var(--card);border-radius:16px;padding:18px 20px;margin-bottom:16px;border-top:4px solid var(--c,var(--accent))}
 .panel h2{font-size:.95rem;margin:0 0 16px;text-transform:uppercase;letter-spacing:.03em;color:var(--c,var(--accent))}
 .panel h2 .right{float:right}
 .panel.p1{--c:#38bdf8}
 .panel.p2{--c:#3b82f6}
 .panel.p3{--c:#818cf8}
 .row{display:flex;flex-wrap:wrap;gap:16px;align-items:flex-end}
 .fld{display:flex;flex-direction:column;font-size:.7rem;gap:5px;color:var(--muted);text-transform:uppercase;letter-spacing:.03em}
 input,select{height:var(--ctl-h);padding:0 12px;border:1px solid #334155;border-radius:8px;font-size:14px;
   background:var(--card2);color:var(--text)}
 input:focus,select:focus{outline:none;border-color:var(--c,var(--accent))}
 input.subject{min-width:240px}
 input.newmail{min-width:260px}
 .btn{height:var(--ctl-h);padding:0 20px;display:inline-flex;align-items:center;justify-content:center;
   background:var(--card2);color:var(--text);border:1px solid #334155;border-radius:8px;
   cursor:pointer;font-size:.82rem;font-weight:600;text-transform:uppercase;letter-spacing:.02em;white-space:nowrap}
 .btn:hover{border-color:var(--c,var(--accent))}
 .btn.alt{background:var(--c,var(--accent));color:#0f172a;border-color:var(--c,var(--accent));font-weight:700}
 .btn.warn{background:rgba(239,68,68,.15);color:#fca5a5;border-color:var(--alarm)}
 .switch{display:inline-flex;align-items:center;gap:8px;font-weight:600;font-size:.9rem;height:var(--ctl-h)}
 .switch input{width:17px;height:17px}
 table.rcp{width:100%;border-collapse:collapse;margin-top:10px}
 table.rcp td,table.rcp th{border-bottom:1px solid #24334a;padding:8px 6px;font-size:.82rem;text-align:left}
 table.rcp th{color:var(--muted);text-transform:uppercase;font-size:.66rem;letter-spacing:.04em}
 .muted{color:var(--muted);font-size:.75rem}
 .msg{font-size:.8rem;margin-left:10px;color:var(--accent)}
 .report{overflow:auto;background:#fff;color:#1f2937;border-radius:10px;padding:14px}
 footer{text-align:center;color:var(--muted);font-size:.72rem;letter-spacing:.14em;
   text-transform:uppercase;font-weight:700;margin-top:18px;padding-top:12px;border-top:1px solid #24334a}
 a{color:var(--accent)}
</style></head><body>
<header>
 <div class=hl>
  <img id=logo src="/logo" alt="" onload="this.style.display='block'">
  <h1>Reportes <span>SGP</span></h1>
 </div>
 <div class=hr>
  <div id=reloj-box><div id=clock>--</div><div id=servidor>ERP ATENEA2 · GRUPO</div></div>
  <a class=salir href="{{url_for('logout')}}">Salir</a>
 </div>
</header>

<nav class=tabs>
 {% for r in reports %}
 <button class=tab data-rid="{{r.id}}" onclick="activate('{{r.id}}')">{{r.name}}</button>
 {% endfor %}
</nav>

{% for r in reports %}
<section class=rep data-rid="{{r.id}}" style="display:none">
 <div class="panel p1">
  <h2>Estado del envío</h2>
  <div class=row>
   <div class=switch>
     <label><input type=checkbox class=enabled onchange="saveCfg('{{r.id}}')"> Envío diario activo</label>
   </div>
   <div class=switch>
     <label><input type=checkbox class=weekdays onchange="saveCfg('{{r.id}}')"> Solo de lunes a viernes</label>
   </div>
   <div class=fld><label>Añadir hora de envío (24h)</label>
     <span style="display:flex;gap:6px;align-items:center">
       <select class=newtime></select>
       <button class="btn alt" onclick="addTime('{{r.id}}')" style="padding:0 14px">Añadir</button>
     </span>
   </div>
   <div class=fld><label>Pausar hasta (incluido)</label><input type=date class=pause_until></div>
   <div class=fld><label>Asunto</label><input type=text class=subject size=26></div>
   <button class="btn alt" onclick="saveCfg('{{r.id}}')">Guardar</button>
   <span class=msg data-k=cfgmsg></span>
  </div>
  <div class=timeslist style="margin-top:12px"></div>
  <p class="muted statusline" style="margin-top:8px"></p>
 </div>

 <div class="panel p2">
  <h2>Destinatarios</h2>
  <div class=row>
   <div class=fld><label>Añadir correo</label><input type=email class=newmail placeholder="nombre@serviplana.es" size=28></div>
   <button class="btn alt" onclick="addMail('{{r.id}}')">Añadir</button>
   <button class="btn warn" onclick="sendNow('{{r.id}}')">Forzar envío</button>
   <span class=msg data-k=sendmsg></span>
  </div>
  <table class=rcp data-k=rcptbl></table>
 </div>

 <div class="panel p3">
  <h2>Reporte (vista en vivo) <button class="btn right" onclick="loadReport('{{r.id}}')">Actualizar</button></h2>
  <div class=report><p class=muted>Cargando…</p></div>
 </div>
</section>
{% endfor %}

<footer>SGP — Departamento IT</footer>
<script>
const REPORTS = {{reports_json|safe}};     // [{id,name}]
const STATE   = {{configs_json|safe}};     // {rid: cfg}
const loaded  = {};
let active = REPORTS.length ? REPORTS[0].id : null;

const DIAS_SEM=["Domingo","Lunes","Martes","Miércoles","Jueves","Viernes","Sábado"];
const MESES_ES=["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"];
function fmtReloj(d){const p=n=>String(n).padStart(2,"0");
 return `${DIAS_SEM[d.getDay()]}, ${d.getDate()} de ${MESES_ES[d.getMonth()]} de ${d.getFullYear()}, ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;}
function tic(){document.getElementById('clock').textContent=fmtReloj(new Date());}
setInterval(tic,1000);tic();

function sec(rid){return document.querySelector(`.rep[data-rid="${rid}"]`);}
function el(rid,sel){return sec(rid).querySelector(sel);}
function flash(rid,k,txt){const n=sec(rid).querySelector(`[data-k="${k}"]`);if(n)n.textContent=txt;}

function activate(rid){
  active=rid;
  REPORTS.forEach(r=>{
    sec(r.id).style.display = (r.id===rid)?'block':'none';
    document.querySelector(`.tab[data-rid="${r.id}"]`).classList.toggle('on', r.id===rid);
  });
  if(!loaded[rid]) loadReport(rid);
}

function fillTimes(rid){
  const sel=el(rid,'.newtime'); if(!sel||sel.options.length) return;
  const p=n=>String(n).padStart(2,'0'); let o='';
  for(let h=0;h<24;h++) for(let m=0;m<60;m+=30) o+=`<option value="${p(h)}:${p(m)}">${p(h)}:${p(m)}</option>`;
  sel.innerHTML=o;
}
function syncInputs(rid){
  const cfg=STATE[rid];
  el(rid,'.enabled').checked = !!cfg.enabled;
  el(rid,'.weekdays').checked = (cfg.weekdays_only!==false);
  el(rid,'.pause_until').value = cfg.pause_until||'';
  el(rid,'.subject').value = cfg.subject||'';
}
function render(rid){
  const cfg=STATE[rid];
  const t=el(rid,'[data-k=rcptbl]');
  let h="<tr><th>Correo</th><th>Activo</th><th></th></tr>";
  (cfg.recipients||[]).forEach((r,i)=>{
    h+=`<tr><td>${r.email}</td>
      <td><input type=checkbox ${r.active?'checked':''} onchange="toggle('${rid}',${i})"></td>
      <td><a href="#" onclick="del('${rid}',${i});return false" style="color:#b0484a">quitar</a></td></tr>`;
  });
  if(!(cfg.recipients||[]).length) h+="<tr><td colspan=3 class=muted>Sin destinatarios</td></tr>";
  t.innerHTML=h;
  renderTimes(rid);
  statusLine(rid);
}
function renderTimes(rid){
  const cfg=STATE[rid];
  const d=el(rid,'.timeslist');
  const chip=(t,i)=>`<span style="display:inline-block;background:var(--card2);border:1px solid #334155;border-radius:20px;padding:4px 12px;margin:0 6px 6px 0;font-size:.85rem">⏰ ${t} <a href="#" onclick="delTime('${rid}',${i});return false" style="color:#b0484a;text-decoration:none;font-weight:700">×</a></span>`;
  const arr=(cfg.send_times||[]);
  d.innerHTML = arr.length ? ('<span class=muted style="margin-right:6px">Horas de envío:</span>'+arr.map(chip).join('')) : '<span class=muted>Sin horas configuradas (no se enviará)</span>';
}
function statusLine(rid){
  const cfg=STATE[rid];
  const s=el(rid,'.statusline');
  const act=(cfg.recipients||[]).filter(r=>r.active).length;
  const horas=(cfg.send_times||[]).join(', ') || '—';
  const dias = (cfg.weekdays_only!==false) ? 'L–V' : 'todos los días';
  let txt = cfg.enabled ? `Envío ACTIVO (${dias}) a las ${horas} · ${act} destinatario(s) activo(s).` : "Envío DESACTIVADO.";
  if(cfg.pause_until) txt += ` En pausa hasta ${cfg.pause_until}.`;
  s.textContent=txt;
}

async function post(rid,cfg){
  const r=await fetch(`api/config/${rid}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(cfg)});
  const j=await r.json(); STATE[rid]=j.config; return j;
}
function collect(rid){
  const cfg=STATE[rid];
  cfg.enabled=el(rid,'.enabled').checked;
  cfg.weekdays_only=el(rid,'.weekdays').checked;
  cfg.pause_until=el(rid,'.pause_until').value||null;
  cfg.subject=el(rid,'.subject').value;
}
async function saveCfg(rid){collect(rid);await post(rid,STATE[rid]);render(rid);syncInputs(rid);flash(rid,'cfgmsg','Guardado ✓');}
async function addTime(rid){
  const inp=el(rid,'.newtime');const t=inp.value;if(!t)return;
  const cfg=STATE[rid];cfg.send_times=cfg.send_times||[];
  if(cfg.send_times.includes(t)){flash(rid,'cfgmsg','Esa hora ya está');return;}
  cfg.send_times.push(t);cfg.send_times.sort();
  await post(rid,cfg);render(rid);flash(rid,'cfgmsg','Hora añadida ✓');
}
async function delTime(rid,i){const cfg=STATE[rid];cfg.send_times.splice(i,1);await post(rid,cfg);render(rid);}
async function addMail(rid){
  const inp=el(rid,'.newmail');const e=inp.value.trim();if(!e)return;
  if(!/^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$/.test(e)){flash(rid,'sendmsg','Correo no válido');return;}
  const cfg=STATE[rid];cfg.recipients=cfg.recipients||[];
  if(cfg.recipients.some(r=>r.email.toLowerCase()===e.toLowerCase())){flash(rid,'sendmsg','Ese correo ya está en la lista');return;}
  cfg.recipients.push({email:e,active:true});inp.value='';
  await post(rid,cfg);render(rid);flash(rid,'sendmsg','Añadido ✓');
}
async function toggle(rid,i){const cfg=STATE[rid];cfg.recipients[i].active=!cfg.recipients[i].active;await post(rid,cfg);render(rid);}
async function del(rid,i){const cfg=STATE[rid];cfg.recipients.splice(i,1);await post(rid,cfg);render(rid);}
async function sendNow(rid){
  flash(rid,'sendmsg','Enviando…');
  const r=await fetch(`api/send-now/${rid}`,{method:'POST'});const j=await r.json();
  flash(rid,'sendmsg', j.ok?('Enviado a: '+j.recipients.join(', ')):('Error: '+j.error));
}
async function loadReport(rid){
  const d=el(rid,'.report');d.innerHTML='<p class=muted>Cargando…</p>';
  try{const r=await fetch(`api/report/${rid}`);const t=await r.text();d.innerHTML=t;loaded[rid]=true;}
  catch(e){d.innerHTML='<p style="color:#b0484a">Error al cargar el reporte</p>';}
}

// init
REPORTS.forEach(r=>{fillTimes(r.id);syncInputs(r.id);render(r.id);});
if(active) activate(active);
</script></body></html>"""


@app.route("/login", methods=["GET", "POST"])
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
    reports = [{"id": r["id"], "name": r["name"]} for r in R.REPORTS]
    configs = {r["id"]: CS.load_config(r["id"]) for r in R.REPORTS}
    return render_template_string(
        PAGE_HTML,
        reports=reports,
        reports_json=json.dumps(reports, ensure_ascii=False),
        configs_json=json.dumps(configs, ensure_ascii=False),
    )


@app.route("/api/report/<rid>")
@login_required
def api_report(rid):
    rep = R.get(rid)
    if not rep:
        abort(404)
    try:
        data = rep["fetch"]()
        return rep["build"](data, full=False)
    except Exception as e:
        return f'<p style="color:#b0484a">Error consultando el ERP: {e}</p>', 200


@app.route("/api/config/<rid>", methods=["POST"])
@login_required
def api_config(rid):
    if not R.get(rid):
        abort(404)
    incoming = request.get_json(force=True, silent=True) or {}
    cfg = _clean_config(incoming, rid)
    CS.save_config(rid, cfg)
    return jsonify(ok=True, config=cfg)


@app.route("/api/send-now/<rid>", methods=["POST"])
@login_required
def api_send_now(rid):
    rep = R.get(rid)
    if not rep:
        abort(404)
    import report_core as core
    cfg = CS.load_config(rid)
    recipients = [r["email"] for r in cfg.get("recipients", []) if r.get("active")]
    try:
        data = rep["fetch"]()
        html = rep["build"](data, full=True)
        sent = core.send_email(html, recipients, cfg.get("subject", rep["subject"]))
        return jsonify(ok=True, recipients=sent)
    except Exception as e:
        return jsonify(ok=False, error=str(e))


@app.route("/logo")
def logo():
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
    app.run(host="0.0.0.0", port=int(os.environ.get("APP_PORT", "8070")))
