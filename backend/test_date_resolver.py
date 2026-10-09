"""Tests del resolvedor de fechas. Ejecutar desde backend/:  python -m unittest test_date_resolver -v"""
import unittest
from datetime import date

from date_resolver import resolve_date

VIERNES = date(2026, 9, 18)
LUNES = date(2026, 9, 14)
DOMINGO = date(2026, 9, 20)


class ResolveDateTest(unittest.TestCase):
    def check(self, text, expected, today=VIERNES):
        result = resolve_date(text, today)
        got = result.value if result else None
        self.assertEqual(got, expected, f"{text!r} (hoy {today}) -> {got}, se esperaba {expected}")

    # --- El bug reportado: nunca debe devolver el lunes ya pasado de esta semana ---
    def test_proximo_lunes_es_el_siguiente_no_el_de_esta_semana(self):
        self.check("Tengo examen el próximo lunes", date(2026, 9, 21))

    def test_proximo_lunes_en_15_dias(self):
        # Hoy + 15 = sábado 3/10 -> primer lunes a partir de ahí.
        self.check("El próximo lunes en 15 días tengo examen", date(2026, 10, 5))
        self.check("En 15 días, el lunes, tengo examen", date(2026, 10, 5))

    # --- Días de la semana ---
    def test_dia_suelto_y_que_viene(self):
        self.check("Reunión con el equipo el lunes", date(2026, 9, 21))
        self.check("El lunes que viene llamo al banco", date(2026, 9, 21))
        self.check("El miércoles hay entrega", date(2026, 9, 23))
        self.check("el miercoles sin tilde", date(2026, 9, 23))

    def test_proximo_mismo_dia_que_hoy_salta_una_semana(self):
        self.check("El próximo viernes voy al médico", date(2026, 9, 25))

    def test_este_dia(self):
        self.check("Este viernes entrego el informe", VIERNES)
        self.check("Este martes entrego el informe", date(2026, 9, 22))

    def test_semana_que_viene_difiere_de_proximo(self):
        self.check("El martes de la semana que viene", date(2026, 9, 22), today=LUNES)
        self.check("El próximo martes", date(2026, 9, 15), today=LUNES)

    def test_casos_limite_lunes_y_domingo(self):
        self.check("el próximo lunes", date(2026, 9, 21), today=LUNES)
        self.check("este lunes", LUNES, today=LUNES)
        self.check("el próximo lunes", date(2026, 9, 21), today=DOMINGO)

    # --- Plazos ---
    def test_plazos(self):
        self.check("En 15 días tengo cita con el dentista", date(2026, 10, 3))
        self.check("en quince días", date(2026, 10, 3))
        self.check("Dentro de dos semanas presento el proyecto", date(2026, 10, 2))
        self.check("en una semana", date(2026, 9, 25))
        self.check("en un mes renuevo el seguro", date(2026, 10, 18))
        self.check("de hoy en 3 días", date(2026, 9, 21))

    def test_mes_ajusta_a_fin_de_mes(self):
        self.check("en un mes", date(2027, 2, 28), today=date(2027, 1, 31))

    # --- Hoy / mañana ---
    def test_manana_y_pasado(self):
        self.check("Mañana entrego el trabajo", date(2026, 9, 19))
        self.check("Pasado mañana compro los regalos", date(2026, 9, 20))
        self.check("Hoy tengo gimnasio", VIERNES)
        self.check("Llamar al banco esta mañana", VIERNES)

    def test_por_la_manana_no_es_manana(self):
        self.check("El lunes por la mañana tengo reunión", date(2026, 9, 21))
        self.check("Mañana por la mañana voy al médico", date(2026, 9, 19))

    # --- Fechas explícitas ---
    def test_fechas_explicitas(self):
        self.check("Entrega el 5 de octubre", date(2026, 10, 5))
        self.check("Cumpleaños el 15 de septiembre", date(2027, 9, 15))  # ya pasó este año
        self.check("Viaje el 3 de enero de 2027", date(2027, 1, 3))

    # --- n-ésimo día de un mes (regresión detectada al probar con Gemini) ---
    def test_nesimo_dia_del_mes(self):
        self.check("Entregar el informe el primer lunes de octubre", date(2026, 10, 5))
        self.check("Reunión el último viernes de septiembre", date(2026, 9, 25))
        self.check("el segundo martes de octubre", date(2026, 10, 13))
        self.check("el primer lunes de septiembre", date(2027, 9, 6))  # ya pasó este año

    def test_dia_con_matices_lo_decide_la_ia(self):
        # Antes la regla genérica respondía "próximo lunes" (21/09), que era incorrecto.
        self.check("el lunes de octubre", None)
        self.check("reenviar el correo del lunes pasado", None)
        self.check("pasado mañana", date(2026, 9, 20))  # "pasado" sin día de la semana sigue funcionando

    # --- Sin fecha reconocible: decide la IA ---
    def test_sin_fecha(self):
        self.check("Comprar leche", None)
        self.check("Entrega el 31 de febrero", None)


if __name__ == "__main__":
    unittest.main()
