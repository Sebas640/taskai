"""Tests de enviar_recordatorios.py (sin red ni base de datos). Desde la raíz del proyecto:
    .venv/Scripts/python -m unittest discover -s automation -v"""
import unittest
from datetime import datetime, timezone
from string import Template

import enviar_recordatorios as er

PLANTILLA = Template((er.AQUI / "plantilla_correo.html").read_text(encoding="utf-8").split("-->", 1)[1])


def fila(**cambios):
    base = {"id": 1, "title": "Entregar informe", "category": "Trabajo", "priority": "Alta",
            "ai_analysis": "Empieza hoy.", "email": "persona@gmail.com", "nombre": "Sebastian",
            "tipo": "dia_anterior", "fecha_legible": "jueves, 8 de octubre"}
    return {**base, **cambios}


class HorarioTest(unittest.TestCase):
    def utc(self, h, m=0):
        return datetime(2026, 10, 9, h, m, tzinfo=timezone.utc)

    def test_limites_de_la_ventana(self):
        # Bogotá = UTC-5: 8:00 Bogotá son las 13:00 UTC; 21:59 Bogotá son las 02:59 UTC del día siguiente.
        self.assertFalse(er.dentro_de_horario(self.utc(12, 59)))  # 7:59
        self.assertTrue(er.dentro_de_horario(self.utc(13, 0)))    # 8:00
        self.assertTrue(er.dentro_de_horario(self.utc(2, 59)))    # 21:59
        self.assertFalse(er.dentro_de_horario(self.utc(3, 0)))    # 22:00


class RenderTest(unittest.TestCase):
    def test_escapa_texto_del_usuario_y_de_la_ia(self):
        h = er.renderizar_html(fila(title='<script>alert("x")</script> & co', ai_analysis="<b>ojo</b>",
                                    priority="<i>Alta</i>"), PLANTILLA, "http://x")
        self.assertNotIn("<script>", h)
        self.assertIn("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; &amp; co", h)
        self.assertIn("&lt;b&gt;ojo&lt;/b&gt;", h)
        self.assertNotIn("<i>Alta</i>", h)

    def test_no_quedan_marcadores_sin_rellenar(self):
        h = er.renderizar_html(fila(), PLANTILLA, "http://x")
        self.assertNotIn("${", h)

    def test_dolar_en_el_titulo_no_rompe_la_plantilla(self):
        h = er.renderizar_html(fila(title="Pagar $50 de ${luz}"), PLANTILLA, "http://x")
        self.assertIn("Pagar $50 de ${luz}", h)

    def test_sin_consejo_no_hay_bloque_de_ia(self):
        self.assertNotIn("Consejo de la IA", er.renderizar_html(fila(ai_analysis=""), PLANTILLA, "http://x"))
        self.assertIn("Consejo de la IA", er.renderizar_html(fila(), PLANTILLA, "http://x"))

    def test_color_y_textos_segun_tipo(self):
        self.assertIn("#dc2626", er.renderizar_html(fila(priority="Alta"), PLANTILLA, "http://x"))
        self.assertIn("<strong>Hoy</strong>", er.renderizar_html(fila(tipo="mismo_dia"), PLANTILLA, "http://x"))

    def test_asunto(self):
        self.assertEqual(er.asunto(fila()), "⏰ Mañana vence: Entregar informe")
        self.assertEqual(er.asunto(fila(tipo="mismo_dia", title="Ir\nal\r\ngym")), "📌 Hoy vence: Ir al gym")

    def test_enmascarar(self):
        self.assertEqual(er.enmascarar("zsebastian@gmail.com"), "zs***@gmail.com")


if __name__ == "__main__":
    unittest.main()
