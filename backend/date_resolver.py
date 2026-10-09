"""
Resolución determinista de fechas relativas en español.

Gemini no es fiable haciendo aritmética de calendario (p. ej. convertía "el próximo
lunes" en el lunes de la semana en curso, ya pasado). Este módulo calcula en Python
las expresiones habituales; solo lo que no reconoce se deja en manos de la IA.

Reglas (las tareas miran al futuro):
- "hoy", "esta tarde/noche/mañana"          -> hoy
- "mañana"                                  -> hoy + 1   ("por la mañana" NO cuenta)
- "pasado mañana"                           -> hoy + 2
- "en / dentro de N días|semanas|meses"     -> hoy + N
- "<día>" / "el próximo <día>" / "que viene"-> primer <día> estrictamente posterior a hoy
- "este <día>"                              -> hoy si hoy es ese día; si no, el siguiente
- "<día> de la semana que viene"            -> ese día de la semana natural siguiente (lunes a domingo)
- "<día> ... en N días" (combinado)         -> primer <día> a partir de hoy + N
- "5 de octubre [de 2027]"                  -> esa fecha (sin año: la próxima vez que ocurra)
- "el primer/último <día> de <mes>"         -> ese día del mes (sin año: la próxima vez que ocurra)

Un día de la semana acompañado de un mes o de "pasado" ("el lunes de octubre",
"el lunes pasado") no se resuelve aquí: lo decide la IA con un calendario de referencia.
"""
import calendar
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

WEEKDAYS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
WEEKDAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
          "septiembre", "octubre", "noviembre", "diciembre"]

NUMBER_WORDS = {
    "un": 1, "una": 1, "uno": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
    "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12, "trece": 13,
    "catorce": 14, "quince": 15, "dieciseis": 16, "diecisiete": 17, "dieciocho": 18,
    "diecinueve": 19, "veinte": 20, "veintiuno": 21, "treinta": 30,
}
_NUM = r"(\d{1,3}|" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")"

_OFFSET = re.compile(
    r"\b(?:en|dentro de|de hoy en|de aqui a)\s+" + _NUM + r"\s+(dias?|semanas?|mes(?:es)?)\b")
_WEEKDAY = re.compile(r"\b(" + "|".join(WEEKDAYS) + r")\b")
_NEXT_WEEK = re.compile(r"\b(?:semana que viene|proxima semana|semana proxima|siguiente semana)\b")
_EXPLICIT = re.compile(
    r"\b(\d{1,2})\s+de\s+(" + "|".join(MONTHS + ["setiembre"]) + r")(?:\s+(?:de|del)\s+(\d{4}))?\b")
_ORDINALS = {"primer": 1, "primero": 1, "segundo": 2, "tercer": 3, "tercero": 3, "cuarto": 4, "ultimo": -1}
_ORDINAL_WEEKDAY = re.compile(
    r"\b(" + "|".join(_ORDINALS) + r")\s+(" + "|".join(WEEKDAYS) + r")\s+de\s+("
    + "|".join(MONTHS + ["setiembre"]) + r")(?:\s+(?:de|del)\s+(\d{4}))?\b")
_ANY_MONTH = re.compile(r"\b(?:" + "|".join(MONTHS + ["setiembre"]) + r")\b")
_DAY_AFTER_TOMORROW = re.compile(r"\bpasado manana\b")
# "mañana" como día siguiente, pero no "por/de/en la mañana" ni "esta mañana".
_TOMORROW = re.compile(r"(?<!la )(?<!esta )\bmanana\b")
_TODAY = re.compile(r"\b(?:hoy|esta tarde|esta noche|esta manana)\b")


@dataclass(frozen=True)
class ResolvedDate:
    value: date
    rule: str  # Qué regla la produjo; útil en logs y tests.


def normalize(text: str) -> str:
    """Minúsculas y sin tildes: 'Miércoles' -> 'miercoles', 'mañana' -> 'manana'."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def _to_int(token: str) -> int:
    return int(token) if token.isdigit() else NUMBER_WORDS[token]


def _add_months(base: date, months: int) -> date:
    month_index = base.month - 1 + months
    year, month = base.year + month_index // 12, month_index % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])  # 31 de enero + 1 mes -> 28/29 feb
    return date(year, month, day)


def _apply_offset(today: date, amount: int, unit: str) -> date:
    if unit.startswith("dia"):
        return today + timedelta(days=amount)
    if unit.startswith("semana"):
        return today + timedelta(weeks=amount)
    return _add_months(today, amount)


def _nth_weekday_of_month(year: int, month: int, weekday: int, n: int) -> Optional[date]:
    """n-ésimo <día> del mes (n = -1: el último). None si no existe (p. ej. un 5.º lunes)."""
    days = [d for d in range(1, calendar.monthrange(year, month)[1] + 1)
            if date(year, month, d).weekday() == weekday]
    if n == -1:
        return date(year, month, days[-1])
    return date(year, month, days[n - 1]) if n <= len(days) else None


def _next_weekday(start: date, weekday: int, include_start: bool) -> date:
    delta = (weekday - start.weekday()) % 7
    if delta == 0 and not include_start:
        delta = 7
    return start + timedelta(days=delta)


def resolve_date(text: str, today: date) -> Optional[ResolvedDate]:
    """Devuelve la fecha de la tarea si el texto contiene una expresión reconocida."""
    t = normalize(text)

    explicit = _EXPLICIT.search(t)
    if explicit:
        day = int(explicit.group(1))
        month_name = "septiembre" if explicit.group(2) == "setiembre" else explicit.group(2)
        month = MONTHS.index(month_name) + 1
        year = int(explicit.group(3)) if explicit.group(3) else today.year
        try:
            value = date(year, month, day)
        except ValueError:
            value = None  # "31 de febrero": no es una fecha, que decida la IA
        if value:
            if not explicit.group(3) and value < today:
                value = date(year + 1, month, day)
            return ResolvedDate(value, "fecha explícita")

    ordinal = _ORDINAL_WEEKDAY.search(t)
    if ordinal:
        n = _ORDINALS[ordinal.group(1)]
        wd = WEEKDAYS.index(ordinal.group(2))
        month_name = "septiembre" if ordinal.group(3) == "setiembre" else ordinal.group(3)
        month = MONTHS.index(month_name) + 1
        year = int(ordinal.group(4)) if ordinal.group(4) else today.year
        value = _nth_weekday_of_month(year, month, wd, n)
        if value and not ordinal.group(4) and value < today:
            value = _nth_weekday_of_month(year + 1, month, wd, n)
        if value:
            return ResolvedDate(value, "n-ésimo día del mes")

    offset = _OFFSET.search(t)
    weekday = _WEEKDAY.search(t)
    # Un día de la semana con matices que estas reglas no modelan ("el lunes de octubre",
    # "el lunes pasado") se deja a la IA: mejor su criterio que una regla que no aplica.
    if weekday and (_ANY_MONTH.search(t) or re.search(weekday.group(1) + r"\s+pasado\b", t)):
        weekday = None

    if offset and weekday:
        target = _apply_offset(today, _to_int(offset.group(1)), offset.group(2))
        wd = WEEKDAYS.index(weekday.group(1))
        return ResolvedDate(_next_weekday(target, wd, include_start=True), "día de la semana + plazo")

    if offset:
        return ResolvedDate(_apply_offset(today, _to_int(offset.group(1)), offset.group(2)), "plazo relativo")

    if _DAY_AFTER_TOMORROW.search(t):
        return ResolvedDate(today + timedelta(days=2), "pasado mañana")
    if _TOMORROW.search(t):
        return ResolvedDate(today + timedelta(days=1), "mañana")
    if _TODAY.search(t):
        return ResolvedDate(today, "hoy")

    if weekday:
        wd = WEEKDAYS.index(weekday.group(1))
        if _NEXT_WEEK.search(t):
            next_monday = today - timedelta(days=today.weekday()) + timedelta(weeks=1)
            return ResolvedDate(next_monday + timedelta(days=wd), "día de la semana que viene")
        says_this = re.search(r"\best[ae]\s+" + weekday.group(1) + r"\b", t)
        return ResolvedDate(
            _next_weekday(today, wd, include_start=bool(says_this)),
            "este día de la semana" if says_this else "próximo día de la semana")

    return None


def describe(value: date) -> str:
    """'lunes, 5 de octubre de 2026' — formato legible en español para el prompt."""
    return f"{WEEKDAYS_ES[value.weekday()]}, {value.day} de {MONTHS[value.month - 1]} de {value.year}"


def calendar_for_prompt(today: date, days: int = 60) -> str:
    """Calendario de referencia para que la IA busque fechas en vez de calcularlas."""
    lines = []
    for i in range(days):
        d = today + timedelta(days=i)
        mark = " (HOY)" if i == 0 else " (MAÑANA)" if i == 1 else ""
        lines.append(f"{d.isoformat()} = {WEEKDAYS_ES[d.weekday()]}{mark}")
    return "\n".join(lines)
