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
os.makedirs(os.path.join(BASE, "salidas"), exist_ok=True)  # asegura la carpeta de logs

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

def horas_envio(cfg):
    """Lista de horas 'HH:MM' configuradas (admite varias al día). Migra del antiguo send_time."""
    ts = cfg.get("send_times")
    if not ts:
        st = cfg.get("send_time")
        ts = [st] if st else []
    return sorted({t.strip() for t in ts if t and ":" in t})

def _enviar(cfg):
    data = core.fetch_data()
    html = core.build_html(data, full=True)
    recipients = [r["email"] for r in cfg.get("recipients", []) if r.get("active")]
    sent = core.send_email(html, recipients, cfg.get("subject", "Previsión de Carga"))
    log(f"Enviado correctamente a: {', '.join(sent)}")

def main():
    cfg   = load_json(CONFIG_PATH, {})
    state = load_json(STATE_PATH, {})
    today = dt.date.today().isoformat()
    force = "--force" in sys.argv   # prueba manual: envía ya, ignora horas/estado
    sent_slots = state.get("sent") or {}   # {hora: fecha_último_envío}

    recipients = [r["email"] for r in cfg.get("recipients", []) if r.get("active")]

    if force:
        if not recipients:
            log("Forzar: no hay destinatarios activos."); return
        try:
            _enviar(cfg)
        except Exception as e:
            log(f"ERROR al enviar (forzado): {e}"); sys.exit(1)
        return

    if not cfg.get("enabled", False):
        return  # desactivado; silencioso
    pause = cfg.get("pause_until")
    if pause and today <= pause:
        return  # en pausa; silencioso

    now_hhmm = dt.datetime.now().strftime("%H:%M")
    # Migración del formato antiguo: si solo había 'last_sent', damos por enviadas
    # las franjas ya vencidas de ese día para no reenviar al actualizar.
    if not sent_slots and state.get("last_sent"):
        sent_slots = {h: state["last_sent"] for h in horas_envio(cfg) if h <= now_hhmm}
    # franjas cuya hora ya pasó hoy y que aún no se han enviado hoy
    due = [h for h in horas_envio(cfg) if now_hhmm >= h and sent_slots.get(h) != today]
    if not due:
        return  # aún no toca ninguna, o ya enviadas

    if not recipients:
        log("No hay destinatarios activos. No se envía."); return

    try:
        _enviar(cfg)                       # un único correo por tick
        for h in due:                      # marca todas las franjas vencidas de hoy
            sent_slots[h] = today
        state["sent"] = sent_slots
        save_state(state)
    except Exception as e:
        log(f"ERROR al enviar: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
