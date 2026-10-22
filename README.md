# Previsión de Carga — Dashboard + envío diario

Dashboard web (siempre visible) que muestra el reporte "Previsión de Carga" del ERP
(ATENEA2 / BBDD GRUPO) en vivo, y permite:
- Gestionar la **lista de destinatarios** (añadir / quitar / activar).
- **Activar o desactivar** el envío diario, fijar la **hora** y **pausar hasta** una fecha.
- **Enviar ahora** (prueba) a los destinatarios activos.

La **ejecución diaria** la hace un cron que lee la configuración del dashboard: envía solo
si el interruptor está activo, no está en pausa, ya pasó la hora y aún no se envió hoy.

## Componentes
- `queries.py` — las 5 consultas del ERP.
- `report_core.py` — núcleo: consulta BD + genera el HTML + envía correo (reutilizado por app y cron).
- `app.py` — dashboard Flask (login, visor en vivo, panel de control). Escribe `config.json`.
- `send_daily.py` — lo ejecuta el cron; lee `config.json` y envía si procede.
- `config.json` — se crea solo desde el dashboard (destinatarios, on/off, hora, pausa, asunto).
- `state.json` — control interno de "último envío" (no tocar).
- `.env` — credenciales BD + SMTP + contraseña del dashboard.

## Instalación (en el Ubuntu, carpeta ~/reporte-carga)
```bash
cd ~/reporte-carga
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

cp .env.example .env && chmod 600 .env
nano .env    # rellena DB_USER/DB_PASSWORD, SMTP_*, APP_PASSWORD y APP_SECRET
```

Genera un APP_SECRET aleatorio:
```bash
python3 -c "import secrets;print(secrets.token_hex(32))"
```

## Arrancar el dashboard (systemd)
```bash
sudo cp systemd/reporte-carga-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now reporte-carga-dashboard
# Visor en: http://<IP-del-servidor>:8070  (login con APP_PASSWORD)
```

## Programar el envío diario (cron cada 10 min)
El cron corre a menudo, pero `send_daily.py` solo envía una vez al día cuando toca.
Así la **hora y el on/off se controlan desde el dashboard** sin tocar el cron.
```bash
crontab -e
*/10 * * * *  /home/mr7/reporte-carga/.venv/bin/python /home/mr7/reporte-carga/send_daily.py >> /home/mr7/reporte-carga/salidas/cron.log 2>&1
```

Prueba manual del envío (ignora hora/estado):
```bash
.venv/bin/python send_daily.py --force
```

## Seguridad
- `.env` con permisos 600; usa una cuenta SQL de **solo lectura** para el ERP.
- El dashboard pide contraseña (APP_PASSWORD). Si va en LAN abierta, considera además
  restringir el puerto 8070 por firewall a la red de confianza.
- El log de envíos queda en `salidas/envio.log`.

## Ajustes
- Mapeo de columnas (STN, Alaplana, Keratile, Vitacer, Venux, C.Logístico 2/3/8, Nave) en
  `report_core.py` (`LABELS`, `CARGA_COLS`, `STOCK_COLS`, `CODE_MAP`). NAV se pliega a STN en
  "En proceso" y se muestra como columna "Nave" en "Almacén".
