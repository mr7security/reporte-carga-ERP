#!/usr/bin/env python3
"""
Envío diario de los reportes. Pensado para cron CADA POCOS MINUTOS (p.ej. */10).
Recorre TODOS los reportes registrados (reports.py); cada uno con su propia
config.<id>.json / state.<id>.json. Cada reporte envía como máximo una vez por
franja horaria y día, cuando:
  - su interruptor está activo (enabled),
  - no está en pausa (pause_until),
  - la hora actual ya alcanzó alguna franja (send_times),
  - y esa franja aún no se ha enviado hoy.

Uso:
  send_daily.py                 -> comprobación normal de todos los reportes
  send_daily.py --force         -> fuerza el envío inmediato de TODOS los reportes
  send_daily.py --force ventas  -> fuerza el envío inmediato solo de ese reporte
"""
import os
import sys
import datetime as dt

BASE = os.path.dirname(os.path.abspath(__file__))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE, ".env"))
except Exception:
    pass

import report_core as core
import reports as R
import configstore as CS

LOG_PATH = os.path.join(BASE, "salidas", "envio.log")
os.makedirs(os.path.join(BASE, "salidas"), exist_ok=True)   # asegura la carpeta de logs


def log(msg):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    line = f"{dt.datetime.now():%Y-%m-%d %H:%M:%S}  {msg}"
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line)


def horas_envio(cfg):
    """Lista de horas 'HH:MM' configuradas (admite varias al día)."""
    ts = cfg.get("send_times")
    if not ts:
        st = cfg.get("send_time")
        ts = [st] if st else []
    return sorted({t.strip() for t in ts if t and ":" in t})


def _enviar(rep, cfg):
    data = rep["fetch"]()
    html = rep["build"](data, full=True)
    recipients = [r["email"] for r in cfg.get("recipients", []) if r.get("active")]
    sent = core.send_email(html, recipients, cfg.get("subject", rep["subject"]))
    log(f"[{rep['id']}] Enviado correctamente a: {', '.join(sent)}")


def procesar(rep, force):
    rid = rep["id"]
    cfg = CS.load_config(rid)
    today = dt.date.today().isoformat()
    recipients = [r["email"] for r in cfg.get("recipients", []) if r.get("active")]

    if force:
        if not recipients:
            log(f"[{rid}] Forzar: no hay destinatarios activos.")
            return
        try:
            _enviar(rep, cfg)
        except Exception as e:
            log(f"[{rid}] ERROR al enviar (forzado): {e}")
        return

    if not cfg.get("enabled", False):
        return  # desactivado; silencioso
    pause = cfg.get("pause_until")
    if pause and today <= pause:
        return  # en pausa; silencioso
    # solo de lunes a viernes (weekday(): lunes=0 … sábado=5, domingo=6)
    if cfg.get("weekdays_only", True) and dt.date.today().weekday() >= 5:
        return  # fin de semana; silencioso

    now_hhmm = dt.datetime.now().strftime("%H:%M")
    state = CS.load_state(rid)
    sent_slots = state.get("sent") or {}   # {hora: fecha_último_envío}
    # franjas cuya hora ya pasó hoy y que aún no se han enviado hoy
    due = [h for h in horas_envio(cfg) if now_hhmm >= h and sent_slots.get(h) != today]
    if not due:
        return  # aún no toca ninguna, o ya enviadas

    if not recipients:
        log(f"[{rid}] No hay destinatarios activos. No se envía.")
        return

    try:
        _enviar(rep, cfg)                  # un único correo por tick
        for h in due:                      # marca todas las franjas vencidas de hoy
            sent_slots[h] = today
        state["sent"] = sent_slots
        CS.save_state(rid, state)
    except Exception as e:
        log(f"[{rid}] ERROR al enviar: {e}")


def main():
    args = sys.argv[1:]
    force = "--force" in args
    target = None
    if force:
        rest = [a for a in args if a != "--force"]
        if rest:
            target = rest[0]            # --force <rid>: fuerza solo ese reporte
    for rep in R.REPORTS:
        if target and rep["id"] != target:
            continue
        procesar(rep, force)


if __name__ == "__main__":
    main()
