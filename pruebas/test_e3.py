"""Pruebas de la Entrega 3. Ejecutar:  python -m unittest discover -s pruebas -t . -v"""
import ast
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import requests

import api_cliente
import repositorio_usuarios as repo
from api_cliente import (ApiClienteError, ApiNoDisponibleError,
                         RespuestaInvalidaError, obtener_json)
from deserializador import DatosInvalidosError, DeserializadorUsuarios
from seguridad import hashear_password, verificar_password

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVOS_PY = [RAIZ / n for n in (
    "api_cliente.py", "deserializador.py", "repositorio_usuarios.py",
    "seguridad.py", "main_e3.py")]


def respuesta(codigo=200, json_data=None, headers=None):
    r = MagicMock()
    r.status_code = codigo
    r.headers = headers or {}
    if json_data is None:
        r.json.side_effect = ValueError("no es json")
    else:
        r.json.return_value = json_data
    return r


def usuario_json(i=1, **extra):
    base = {"id": i, "name": f"Usuario {i}", "username": f"user{i}",
            "email": f"user{i}@ejemplo.com", "phone": "123",
            "website": "ejemplo.com", "company": {"name": "Acme"}}
    base.update(extra)
    return base


class PruebasCliente(unittest.TestCase):
    def setUp(self):
        self.dormir = MagicMock()

    @patch("api_cliente.requests.get")
    def test_exito_envia_timeout(self, get):
        get.return_value = respuesta(200, [{"id": 1}])
        self.assertEqual(obtener_json("http://x", dormir=self.dormir), [{"id": 1}])
        self.assertEqual(get.call_args.kwargs["timeout"], api_cliente.TIMEOUT)
        self.dormir.assert_not_called()

    @patch("api_cliente.requests.get")
    def test_4xx_no_reintenta(self, get):
        get.return_value = respuesta(404)
        with self.assertRaises(ApiClienteError) as ctx:
            obtener_json("http://x", dormir=self.dormir)
        self.assertEqual(ctx.exception.status, 404)
        self.assertEqual(get.call_count, 1)
        self.dormir.assert_not_called()

    @patch("api_cliente.requests.get")
    def test_5xx_reintenta_con_backoff_exponencial(self, get):
        get.return_value = respuesta(503)
        with self.assertRaises(ApiNoDisponibleError):
            obtener_json("http://x", max_intentos=4, dormir=self.dormir)
        self.assertEqual(get.call_count, 4)
        esperas = [c.args[0] for c in self.dormir.call_args_list]
        self.assertEqual(esperas, [1, 2, 4])

    @patch("api_cliente.requests.get")
    def test_429_respeta_retry_after(self, get):
        get.side_effect = [respuesta(429, headers={"Retry-After": "7"}),
                           respuesta(200, [])]
        self.assertEqual(obtener_json("http://x", dormir=self.dormir), [])
        self.dormir.assert_called_once_with(7.0)

    @patch("api_cliente.requests.get")
    def test_sin_red_reintenta_y_falla_controlado(self, get):
        get.side_effect = requests.exceptions.ConnectionError("sin wifi")
        with self.assertRaises(ApiNoDisponibleError):
            obtener_json("http://x", max_intentos=3, dormir=self.dormir)
        self.assertEqual(get.call_count, 3)

    @patch("api_cliente.requests.get")
    def test_recupera_tras_fallo_temporal(self, get):
        get.side_effect = [requests.exceptions.Timeout(), respuesta(200, [1])]
        self.assertEqual(obtener_json("http://x", dormir=self.dormir), [1])
        self.assertEqual(get.call_count, 2)

    def test_url_invalida_no_reintenta(self):
        with self.assertRaises(ApiClienteError):
            obtener_json("esto-no-es-una-url", dormir=self.dormir)
        self.dormir.assert_not_called()

    @patch("api_cliente.requests.get")
    def test_json_invalido(self, get):
        get.return_value = respuesta(200, None)
        with self.assertRaises(RespuestaInvalidaError):
            obtener_json("http://x", dormir=self.dormir)


class PruebasDeserializador(unittest.TestCase):
    def setUp(self):
        self.d = DeserializadorUsuarios()

    def test_valido(self):
        u = self.d.desde_dict(usuario_json(1, email="ANA@Ejemplo.com"))
        self.assertEqual((u.id_api, u.email, u.empresa), (1, "ana@ejemplo.com", "Acme"))

    def test_invalidos(self):
        for malo in (usuario_json(0), usuario_json(1, email="sin-arroba"),
                     usuario_json(1, name=""), "texto", usuario_json(True)):
            with self.assertRaises(DatosInvalidosError):
                self.d.desde_dict(malo)

    def test_lista_descarta_solo_el_malo(self):
        validos, rechazados = self.d.desde_lista(
            [usuario_json(1), usuario_json(2, email="x"), usuario_json(3)])
        self.assertEqual([u.id_api for u in validos], [1, 3])
        self.assertEqual(len(rechazados), 1)


class PruebasBaseDeDatos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patcher = patch.dict(os.environ, {"DB_PATH": os.path.join(self.tmp.name, "t.db")})
        self.patcher.start()
        repo.crear_tablas()
        d = DeserializadorUsuarios()
        self.usuarios, _ = d.desde_lista([usuario_json(i) for i in (1, 2, 3)])

    def tearDown(self):
        self.patcher.stop()
        self.tmp.cleanup()

    def test_idempotencia(self):
        self.assertEqual(repo.guardar_usuarios(self.usuarios, "clave-demo"), (3, 0))
        self.assertEqual(repo.guardar_usuarios(self.usuarios, "clave-demo"), (0, 3))
        self.assertEqual(len(repo.listar_usuarios()), 3)

    def test_segunda_ejecucion_no_cambia_el_hash(self):
        repo.guardar_usuarios(self.usuarios, "clave-demo")
        antes = repo.obtener_hash("user1")
        repo.guardar_usuarios(self.usuarios, "otra-clave")
        self.assertEqual(antes, repo.obtener_hash("user1"))

    def test_sin_contrasenas_en_texto_plano(self):
        repo.guardar_usuarios(self.usuarios, "clave-demo")
        with sqlite3.connect(os.environ["DB_PATH"]) as conn:
            hashes = [f[0] for f in conn.execute("SELECT password_hash FROM usuario")]
        self.assertEqual(len(hashes), 3)
        for h in hashes:
            self.assertNotIn("clave-demo", h)
            self.assertTrue(h.startswith("$2"))
        self.assertEqual(len(set(hashes)), 3, "cada hash debe tener su propio salt")

    def test_login(self):
        repo.guardar_usuarios(self.usuarios, "clave-demo")
        h = repo.obtener_hash("user2")
        self.assertTrue(verificar_password("clave-demo", h))
        self.assertFalse(verificar_password("incorrecta", h))
        self.assertFalse(verificar_password("clave-demo", "hash-roto"))

    def test_inyeccion_sql_en_obtener_hash(self):
        repo.guardar_usuarios(self.usuarios, "clave-demo")
        self.assertIsNone(repo.obtener_hash("' OR '1'='1"))

    def test_hash_rechaza_vacia(self):
        with self.assertRaises(ValueError):
            hashear_password("")


class PruebasAuditoriaEstatica(unittest.TestCase):
    """Busca en el código las señales de riesgo típicas de código generado por IA."""

    def arboles(self):
        for ruta in ARCHIVOS_PY:
            yield ruta, ast.parse(ruta.read_text(encoding="utf-8"))

    def test_sin_sql_armado_con_texto_dinamico(self):
        for ruta, arbol in self.arboles():
            for nodo in ast.walk(arbol):
                if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
                        and nodo.func.attr in ("execute", "executemany", "executescript")
                        and nodo.args):
                    arg = nodo.args[0]
                    peligroso = isinstance(arg, (ast.JoinedStr, ast.BinOp)) or (
                        isinstance(arg, ast.Call) and isinstance(arg.func, ast.Attribute)
                        and arg.func.attr == "format")
                    self.assertFalse(peligroso, f"SQL dinámico en {ruta.name}:{nodo.lineno}")

    def test_sin_verify_false(self):
        for ruta, arbol in self.arboles():
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.keyword) and nodo.arg == "verify":
                    self.assertNotIsInstance(nodo.value, ast.Constant)
                    if isinstance(nodo.value, ast.Constant):
                        self.assertIsNot(nodo.value.value, False)

    def test_sin_except_generico(self):
        for ruta, arbol in self.arboles():
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.ExceptHandler):
                    self.assertIsNotNone(nodo.type, f"except vacío en {ruta.name}:{nodo.lineno}")
                    if isinstance(nodo.type, ast.Name):
                        self.assertNotIn(nodo.type.id, ("Exception", "BaseException"))
                    cuerpo_pass = all(isinstance(n, ast.Pass) for n in nodo.body)
                    if cuerpo_pass:
                        # solo se permite pass para ImportError opcional (python-dotenv)
                        self.assertEqual(getattr(nodo.type, "id", None), "ImportError")

    def test_toda_llamada_requests_lleva_timeout(self):
        for ruta, arbol in self.arboles():
            for nodo in ast.walk(arbol):
                if (isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Attribute)
                        and isinstance(nodo.func.value, ast.Name)
                        and nodo.func.value.id == "requests"
                        and nodo.func.attr in ("get", "post", "put", "delete", "patch", "request")):
                    nombres = [k.arg for k in nodo.keywords]
                    self.assertIn("timeout", nombres, f"sin timeout en {ruta.name}:{nodo.lineno}")

    def test_env_no_esta_en_el_proyecto(self):
        self.assertFalse((RAIZ / ".env").exists(), "el archivo .env no debe subirse")


if __name__ == "__main__":
    unittest.main()
