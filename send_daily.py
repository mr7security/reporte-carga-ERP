#!/usr/bin/env python3
"""
Envío diario del reporte. Pensado para cron CADA POCOS MINUTOS (p.ej. */10).
Envía como máximo una vez al día, cuando:
  - el interruptor está activo (enabled),
  - no está en pausa (pause_until),
  - la hora actual ya alcanzó send_time,
  - y hoy aún no se ha enviado.
Así la hora/activación se controlan desde el dashboard sin tocar el cron.
"""
import os, json, sys, datetime as dt

BASE = os.path.dirname(os.path.abspath(__file__))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE, ".env"))
except Exception:
    pass

import report_core as core

CONFIG_PATH = os.path.join(BASE, "config.json")
STATE_PATH  = os.path.join(BASE, "state.json")
LOG_PATH    = os.path.join(BASE, "salidas", "envio.log")

def log(msg):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)

def load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f)

def main():
    cfg   = load_json(CONFIG_PATH, {})
    state = load_json(STATE_PATH, {})
    today = dt.date.today().isoformat()
    force = "--force" in sys.argv   # para pruebas manuales: ignora hora/estado

    if not cfg.get("enabled", False):
        log("Envío desactivado (enabled=false). No se envía."); return
    pause = cfg.get("pause_until")
    if pause and today <= pause and not force:
        log(f"En pausa hasta {pause}. No se envía hoy."); return
    if state.get("last_sent") == today and not force:
        return  # ya enviado hoy; silencioso para no llenar el log
    send_time = cfg.get("send_time", "07:30")
    if not force and dt.datetime.now().strftime("%H:%M") < send_time:
        return  # aún no es la hora; silencioso

    recipients = [r["email"] for r in cfg.get("recipients", []) if r.get("active")]
    if not recipients:
        log("No hay destinatarios activos. No se envía."); return

    try:
        data = core.fetch_data()
        html = core.build_html(data, full=True)
        sent = core.send_email(html, recipients, cfg.get("subject", "Previsión de Carga"))
        state["last_sent"] = today
        save_state(state)
        log(f"Enviado correctamente a: {', '.join(sent)}")
    except Exception as e:
        log(f"ERROR al enviar: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
