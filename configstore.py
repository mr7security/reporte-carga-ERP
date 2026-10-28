#!/usr/bin/env python3
"""
Configuración y estado por reporte.
Cada reporte tiene su propio config.<id>.json y state.<id>.json, de modo que
"Previsión de Carga" y "Ventas (Alb)" se activan, pausan y programan por separado.

Migración: la primera vez que se pide 'carga', si aún no existe config.carga.json
se copia del antiguo config.json (y state.json -> state.carga.json), para no
perder la configuración actual.
"""
import os
import json
import shutil

BASE = os.path.dirname(os.path.abspath(__file__))

# Valores por defecto por reporte
DEFAULTS = {
    "carga":  {"enabled": True, "send_times": ["07:30"], "pause_until": None,
               "subject": "Previsión de Carga", "recipients": []},
    "ventas": {"enabled": True, "send_times": [], "pause_until": None,
               "subject": "Ventas (Alb)", "recipients": []},
}
_BASE_DEFAULT = {"enabled": True, "send_times": [], "pause_until": None,
                 "subject": "Reporte", "recipients": []}


def _default(rid):
    d = dict(_BASE_DEFAULT)
    d.update(DEFAULTS.get(rid, {}))
    return d


def config_path(rid):
    return os.path.join(BASE, f"config.{rid}.json")


def state_path(rid):
    return os.path.join(BASE, f"state.{rid}.json")


def _migrate_legacy(rid):
    """Para 'carga', hereda el antiguo config.json / state.json si aún no hay fichero nuevo."""
    if rid != "carga":
        return
    for legacy, new in ((os.path.join(BASE, "config.json"), config_path("carga")),
                        (os.path.join(BASE, "state.json"),  state_path("carga"))):
        try:
            if not os.path.exists(new) and os.path.exists(legacy):
                shutil.copyfile(legacy, new)
        except Exception:
            pass


def load_config(rid):
    _migrate_legacy(rid)
    d = _default(rid)
    try:
        with open(config_path(rid), encoding="utf-8") as f:
            cfg = json.load(f)
        for k, v in d.items():
            cfg.setdefault(k, v)
        # migración del antiguo campo único "send_time"
        if not cfg.get("send_times"):
            st = cfg.get("send_time")
            cfg["send_times"] = [st] if st else []
        cfg.pop("send_time", None)
        return cfg
    except Exception:
        return d


def save_config(rid, cfg):
    p = config_path(rid)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)


def load_state(rid):
    _migrate_legacy(rid)
    try:
        with open(state_path(rid), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(rid, state):
    p = state_path(rid)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f)
    os.replace(tmp, p)
