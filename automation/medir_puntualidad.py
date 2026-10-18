"""
Mide la puntualidad de las ejecuciones programadas de los recordatorios en GitHub Actions y compara
antes y después de un cambio de horario. Solo usa la API pública de GitHub (sin token).

    python automation/medir_puntualidad.py
    python automation/medir_puntualidad.py --cambio 2026-10-18T13:50:45-05:00

Indicadores:
  - Cobertura: de las ejecuciones que tocaban (14 al día), cuántas hizo GitHub realmente.
  - Retraso: minutos entre la hora programada y la hora real de inicio.

Hasta el cambio el horario era a las :00; desde el cambio, a las :17. Cada ejecución se atribuye a la
última hora programada anterior a su inicio (si GitHub la retrasara más de una hora, se contaría en
la hora siguiente: es una aproximación).
"""
import argparse
import json
import statistics
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = "Sebas640/taskai"
HORAS_UTC = set(range(13, 24)) | {0, 1, 2}  # 8:00-21:00 de Bogotá
CAMBIO_POR_DEFECTO = "2026-10-18T13:50:45-05:00"  # commit d71c46a: de :00 a :17


def ejecuciones_programadas() -> list[datetime]:
    inicios, pagina = [], 1
    while True:
        url = (f"https://api.github.com/repos/{REPO}/actions/runs"
               f"?event=schedule&per_page=100&page={pagina}")
        with urllib.request.urlopen(url, timeout=30) as resp:
            runs = json.load(resp)["workflow_runs"]
        inicios += [datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")) for r in runs]
        if len(runs) < 100:
            return sorted(inicios)
        pagina += 1


def franjas(desde: datetime, hasta: datetime, minuto: int) -> list[datetime]:
    """Horas programadas (UTC) en [desde, hasta)."""
    t = desde.replace(minute=minuto, second=0, microsecond=0)
    if t < desde:
        t += timedelta(hours=1)
    resultado = []
    while t < hasta:
        if t.hour in HORAS_UTC:
            resultado.append(t)
        t += timedelta(hours=1)
    return resultado


def resumir(nombre: str, inicios: list[datetime], desde: datetime, hasta: datetime, minuto: int) -> None:
    esperadas = franjas(desde, hasta, minuto)
    atribuidas, retrasos = set(), []
    for inicio in inicios:
        franja = inicio.replace(minute=minuto, second=0, microsecond=0)
        if franja > inicio:
            franja -= timedelta(hours=1)
        atribuidas.add(franja)
        retrasos.append((inicio - franja).total_seconds() / 60)
    hechas = len(atribuidas & set(esperadas))
    print(f"\n{nombre} (horario a las :{minuto:02d})")
    print(f"  Periodo:   {desde.astimezone(BOGOTA):%d/%m %H:%M} -> {hasta.astimezone(BOGOTA):%d/%m %H:%M} (Bogotá)")
    if not esperadas:
        print("  Sin franjas en este periodo todavía.")
        return
    print(f"  Cobertura: {hechas} de {len(esperadas)} ejecuciones = {100 * hechas / len(esperadas):.0f} %"
          f"  (~{14 * hechas / len(esperadas):.1f} de 14 al día)")
    if retrasos:
        print(f"  Retraso:   mediana {statistics.median(retrasos):.0f} min | máximo {max(retrasos):.0f} min")
    if len(esperadas) < 28:
        print(f"  ⚠ Pocos datos ({len(esperadas)} franjas): espera a tener al menos 2 días para concluir.")


BOGOTA = timezone(timedelta(hours=-5))

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cambio", default=CAMBIO_POR_DEFECTO, help="momento del cambio de horario (ISO 8601)")
    cambio = datetime.fromisoformat(p.parse_args().cambio).astimezone(timezone.utc)
    ahora = datetime.now(timezone.utc)

    inicios = ejecuciones_programadas()
    if not inicios:
        raise SystemExit("No hay ejecuciones programadas todavía.")
    antes = [t for t in inicios if t < cambio]
    despues = [t for t in inicios if t >= cambio]
    resumir("ANTES", antes, antes[0] if antes else cambio, cambio, 0)
    resumir("DESPUÉS", despues, cambio, ahora, 17)
