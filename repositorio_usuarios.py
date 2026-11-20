"""Persistencia SQLite de los usuarios obtenidos desde la API.

* Todas las consultas son literales completos con marcadores `?`
  (cero concatenación, cero f-strings dentro de execute()).
* La operación de guardado es idempotente: ejecutarla dos veces no duplica filas.
* Las contraseñas se guardan SIEMPRE como hash bcrypt.
"""
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from seguridad import hashear_password

SQL_CREAR_TABLA = """
CREATE TABLE IF NOT EXISTS usuario (
    id_api        INTEGER PRIMARY KEY,
    nombre        TEXT NOT NULL,
    username      TEXT NOT NULL,
    email         TEXT NOT NULL,
    telefono      TEXT,
    sitio_web     TEXT,
    empresa       TEXT,
    password_hash TEXT NOT NULL,
    obtenido_en   TEXT NOT NULL
)
"""

SQL_EXISTE = "SELECT 1 FROM usuario WHERE id_api = ?"

SQL_INSERTAR = (
    "INSERT INTO usuario (id_api, nombre, username, email, telefono, sitio_web, "
    "empresa, password_hash, obtenido_en) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)

# Al actualizar NO se toca password_hash: así la segunda ejecución no cambia contraseñas.
SQL_ACTUALIZAR = (
    "UPDATE usuario SET nombre = ?, username = ?, email = ?, telefono = ?, "
    "sitio_web = ?, empresa = ?, obtenido_en = ? WHERE id_api = ?"
)

SQL_LISTAR = (
    "SELECT id_api, nombre, username, email, empresa, obtenido_en "
    "FROM usuario ORDER BY id_api"
)

SQL_OBTENER_HASH = "SELECT password_hash FROM usuario WHERE username = ?"


def ruta_bd():
    return os.getenv("DB_PATH", "ecotech.db")


@contextmanager
def obtener_conexion():
    """Transacción: commit si todo sale bien, rollback ante cualquier excepción."""
    conn = sqlite3.connect(ruta_bd())
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            yield conn
    finally:
        conn.close()


def ahora_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def crear_tablas():
    with obtener_conexion() as conn:
        conn.execute(SQL_CREAR_TABLA)


def guardar_usuarios(usuarios, password_inicial):
    """Inserta los nuevos y actualiza los existentes, todo en UNA transacción.

    Devuelve (insertados, actualizados). El hash bcrypt solo se calcula para
    usuarios nuevos (es lento a propósito).
    """
    marca_tiempo = ahora_utc()
    insertados = actualizados = 0

    with obtener_conexion() as conn:
        for u in usuarios:
            existe = conn.execute(SQL_EXISTE, (u.id_api,)).fetchone()
            if existe:
                conn.execute(SQL_ACTUALIZAR, (
                    u.nombre, u.username, u.email, u.telefono,
                    u.sitio_web, u.empresa, marca_tiempo, u.id_api))
                actualizados += 1
            else:
                conn.execute(SQL_INSERTAR, (
                    u.id_api, u.nombre, u.username, u.email, u.telefono,
                    u.sitio_web, u.empresa,
                    hashear_password(password_inicial), marca_tiempo))
                insertados += 1
    return insertados, actualizados


def listar_usuarios():
    """Lee los datos locales (Plan B). Devuelve una lista de tuplas."""
    with obtener_conexion() as conn:
        return conn.execute(SQL_LISTAR).fetchall()


def obtener_hash(username):
    with obtener_conexion() as conn:
        fila = conn.execute(SQL_OBTENER_HASH, (username,)).fetchone()
    return fila[0] if fila else None
