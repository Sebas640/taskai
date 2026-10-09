"""
Envía por correo los recordatorios de TaskAI: tareas sin completar que vencen mañana (aviso del día
anterior) u hoy (aviso del mismo día). Lo ejecuta GitHub Actions cada hora (.github/workflows/
recordatorios.yml) para que funcione aunque el PC esté apagado; también se puede lanzar a mano.

Variables de entorno:
    DATABASE_URL        conexión a PostgreSQL (Neon)
    GMAIL_USER          cuenta de Gmail que envía
    GMAIL_APP_PASSWORD  contraseña de aplicación de esa cuenta
    APP_URL             (opcional) enlace del botón "Ver mis tareas"

Uso:
    python automation/enviar_recordatorios.py              # envía (solo entre las 8:00 y las 21:59 de Bogotá)
    python automation/enviar_recordatorios.py --forzar     # envía a cualquier hora
    python automation/enviar_recordatorios.py --dry-run    # simula: no envía ni marca; guarda vistas previas
"""
import argparse
import html
import os
import smtplib
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from string import Template

import psycopg2
import psycopg2.extras

AQUI = Path(__file__).parent

# Bogotá está en UTC-5 todo el año (sin horario de verano): no hace falta base de datos de zonas.
BOGOTA = timezone(timedelta(hours=-5), "America/Bogota")
HORA_INICIO, HORA_FIN = 8, 21  # se envía de 8:00 a 21:59

COLOR_PRIORIDAD = {"Alta": "#dc2626", "Media": "#d97706", "Baja": "#16a34a"}

SQL_MARCAR = """
UPDATE tasks SET
  reminder_day_before_sent_at = CASE WHEN %(tipo)s = 'dia_anterior' THEN NOW() ELSE reminder_day_before_sent_at END,
  reminder_same_day_sent_at   = CASE WHEN %(tipo)s = 'mismo_dia'    THEN NOW() ELSE reminder_same_day_sent_at END
WHERE id = %(id)s
"""


def enmascarar(correo: str) -> str:
    """'zsebastian@gmail.com' -> 'zs***@gmail.com': los logs de GitHub Actions no deben exponer correos."""
    usuario, _, dominio = correo.partition("@")
    return f"{usuario[:2]}***@{dominio}"


def dentro_de_horario(ahora: datetime) -> bool:
    return HORA_INICIO <= ahora.astimezone(BOGOTA).hour <= HORA_FIN


def asunto(r: dict) -> str:
    prefijo = "⏰ Mañana vence: " if r["tipo"] == "dia_anterior" else "📌 Hoy vence: "
    return prefijo + " ".join(r["title"].split())  # sin saltos de línea: romperían la cabecera


def renderizar_html(r: dict, plantilla: Template, url_app: str) -> str:
    e = html.escape  # todo texto viene del usuario o de la IA
    intro = ("⏰ <strong>Mañana</strong> vence una de tus tareas:" if r["tipo"] == "dia_anterior"
             else "📌 <strong>Hoy</strong> vence una de tus tareas:")
    consejo = r.get("ai_analysis") or ""
    bloque_consejo = (
        '<p style="margin:18px 0 0;padding:12px 14px;background:#eff6ff;border-left:3px solid #60a5fa;'
        'border-radius:8px;font-size:14px;color:#1e3a8a;">🤖 <strong>Consejo de la IA:</strong> '
        f"{e(consejo)}</p>" if consejo.strip() else "")
    return plantilla.substitute(
        nombre=e(r["nombre"]), intro=intro, titulo=e(r["title"]), fecha=e(r["fecha_legible"]),
        categoria=e(r["category"]), prioridad=e(r["priority"]),
        color_prioridad=COLOR_PRIORIDAD.get(r["priority"], "#64748b"),
        bloque_consejo=bloque_consejo, url_app=e(url_app, quote=True))


def renderizar_texto(r: dict, url_app: str) -> str:
    """Versión de texto plano, para clientes que no muestran HTML (y ayuda contra el spam)."""
    cuando = "Mañana" if r["tipo"] == "dia_anterior" else "Hoy"
    lineas = [f"Hola {r['nombre']},", "", f"{cuando} vence una de tus tareas:", "",
              f"  {r['title']}", f"  Fecha: {r['fecha_legible']}",
              f"  Categoría: {r['category']} · Prioridad {r['priority']}"]
    if (r.get("ai_analysis") or "").strip():
        lineas += ["", f"Consejo de la IA: {r['ai_analysis']}"]
    lineas += ["", f"Ver mis tareas: {url_app}"]
    return "\n".join(lineas)


def buscar_pendientes(conn) -> list[dict]:
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute((AQUI / "buscar_recordatorios.sql").read_text(encoding="utf-8"))
        return [dict(r) for r in cur.fetchall()]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="simula: no envía correos ni marca tareas")
    p.add_argument("--forzar", action="store_true", help="ignora la ventana horaria 8:00-21:59")
    args = p.parse_args()

    ahora = datetime.now(timezone.utc)
    print(f"Hora en Bogotá: {ahora.astimezone(BOGOTA):%Y-%m-%d %H:%M}")
    if not args.forzar and not dentro_de_horario(ahora):
        print("Fuera del horario de envío (8:00-21:59 Bogotá): no se hace nada.")
        return 0

    url_app = os.getenv("APP_URL") or "http://localhost:4200/tasks"
    plantilla = Template((AQUI / "plantilla_correo.html").read_text(encoding="utf-8").split("-->", 1)[1].lstrip())

    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute("SET TIME ZONE 'America/Bogota'")  # Neon usa UTC; las fechas de tareas son de Bogotá
        pendientes = buscar_pendientes(conn)
        print(f"Recordatorios pendientes: {len(pendientes)}")
        if not pendientes:
            return 0

        if args.dry_run:
            carpeta = Path(tempfile.mkdtemp(prefix="taskai_vista_"))
            for r in pendientes:
                (carpeta / f"tarea_{r['id']}_{r['tipo']}.html").write_text(
                    renderizar_html(r, plantilla, url_app), encoding="utf-8")
                print(f"  [SIMULACIÓN] {enmascarar(r['email'])} | {asunto(r)}")
            print(f"Vistas previas en: {carpeta}")
            return 0

        usuario, clave = os.environ["GMAIL_USER"], os.environ["GMAIL_APP_PASSWORD"].replace(" ", "")
        fallos = 0
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
            smtp.login(usuario, clave)
            for r in pendientes:
                msg = EmailMessage()
                msg["From"] = f"TaskAI <{usuario}>"
                msg["To"] = r["email"]
                msg["Subject"] = asunto(r)
                msg.set_content(renderizar_texto(r, url_app))
                msg.add_alternative(renderizar_html(r, plantilla, url_app), subtype="html")
                try:
                    smtp.send_message(msg)
                except smtplib.SMTPException as exc:
                    # Sin marcar: se reintentará en la próxima ejecución.
                    fallos += 1
                    print(f"  ERROR enviando a {enmascarar(r['email'])} (tarea {r['id']}): {exc}")
                    continue
                with conn.cursor() as cur:
                    cur.execute(SQL_MARCAR, {"tipo": r["tipo"], "id": r["id"]})
                conn.commit()  # tras cada envío: si algo falla después, lo enviado ya consta
                print(f"  Enviado a {enmascarar(r['email'])} | tarea {r['id']} | {r['tipo']}")
        print(f"Enviados: {len(pendientes) - fallos} | Fallidos: {fallos}")
        return 1 if fallos else 0  # código 1 = la ejecución aparece en rojo en GitHub
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
