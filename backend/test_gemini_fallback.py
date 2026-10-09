"""Tests del respaldo entre modelos de Gemini, sin llamar a la API (se simulan sus respuestas).
Ejecutar desde backend/:  python -m unittest test_gemini_fallback -v"""
import asyncio
import json
import unittest
from unittest.mock import MagicMock, patch

from fastapi import HTTPException
from google.genai import errors

import main


def api_error(code, status):
    cls = errors.ServerError if code >= 500 else errors.ClientError
    return cls(code, {"error": {"code": code, "message": f"simulado {code}", "status": status}})


def ok_response():
    r = MagicMock()
    r.text = json.dumps({"title": "Entregar informe", "category": "Trabajo", "priority": "Alta",
                         "detected_date": None, "ai_analysis": "Empieza hoy."})
    return r


class FakeDB:
    def add(self, obj): pass
    def commit(self): pass
    def refresh(self, obj): obj.id = 1
    def rollback(self): pass


class FakeUser:
    id = 1


def run_endpoint():
    return asyncio.run(main.process_and_save(main.TaskRequest(text="Mañana entrego el informe"), FakeDB(), FakeUser()))


class FallbackTest(unittest.TestCase):
    def models_called(self, mock):
        return [c.kwargs["model"] for c in mock.call_args_list]

    def test_503_pasa_al_siguiente_modelo(self):
        with patch.object(main.client.models, "generate_content",
                          side_effect=[api_error(503, "UNAVAILABLE"), ok_response()]) as m:
            run_endpoint()
        self.assertEqual(self.models_called(m), main.GEMINI_MODELS[:2])

    def test_429_cuota_agotada_pasa_al_siguiente_modelo(self):
        with patch.object(main.client.models, "generate_content",
                          side_effect=[api_error(429, "RESOURCE_EXHAUSTED"), ok_response()]) as m:
            run_endpoint()
        self.assertEqual(len(m.call_args_list), 2)

    def test_error_400_no_prueba_otros_modelos(self):
        with patch.object(main.client.models, "generate_content",
                          side_effect=[api_error(400, "INVALID_ARGUMENT")]) as m:
            with self.assertRaises(HTTPException) as ctx:
                run_endpoint()
        self.assertEqual(len(m.call_args_list), 1)
        self.assertEqual(ctx.exception.status_code, 502)

    def test_todos_saturados_devuelve_503_comprensible(self):
        with patch.object(main.client.models, "generate_content",
                          side_effect=[api_error(503, "UNAVAILABLE")] * len(main.GEMINI_MODELS)) as m:
            with self.assertRaises(HTTPException) as ctx:
                run_endpoint()
        self.assertEqual(self.models_called(m), main.GEMINI_MODELS)
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("saturada", ctx.exception.detail)

    def test_todos_sin_cuota_devuelve_429_comprensible(self):
        with patch.object(main.client.models, "generate_content",
                          side_effect=[api_error(429, "RESOURCE_EXHAUSTED")] * len(main.GEMINI_MODELS)):
            with self.assertRaises(HTTPException) as ctx:
                run_endpoint()
        self.assertEqual(ctx.exception.status_code, 429)
        self.assertIn("cuota", ctx.exception.detail)

    def test_primer_modelo_responde_sin_respaldo(self):
        with patch.object(main.client.models, "generate_content", side_effect=[ok_response()]) as m:
            r = run_endpoint()
        self.assertEqual(self.models_called(m), main.GEMINI_MODELS[:1])
        self.assertEqual(r["title"], "Entregar informe")


if __name__ == "__main__":
    unittest.main()
