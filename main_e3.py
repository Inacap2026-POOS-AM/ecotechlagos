
import getpass
import logging
import os
import secrets
import sqlite3
import sys
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # python-dotenv es opcional: sin él se usan los valores por defecto
    pass

from api_cliente import (ApiClienteError, ApiError, ApiNoDisponibleError,
                         RespuestaInvalidaError, obtener_json)
from deserializador import DatosInvalidosError, DeserializadorUsuarios
from repositorio_usuarios import (crear_tablas, guardar_usuarios,
                                  listar_usuarios, obtener_hash)
from seguridad import verificar_password

URL_POR_DEFECTO = "https://jsonplaceholder.typicode.com/users"


def antiguedad(obtenido_en):
    """Convierte la fecha ISO guardada en un texto tipo 'hace 5 min'."""
    try:
        momento = datetime.fromisoformat(obtenido_en)
    except (TypeError, ValueError):
        return "fecha desconocida"
    segundos = int((datetime.now(timezone.utc) - momento).total_seconds())
    if segundos < 60:
        return f"hace {max(segundos, 0)} s"
    if segundos < 3600:
        return f"hace {segundos // 60} min"
    if segundos < 86400:
        return f"hace {segundos // 3600} h"
    return f"hace {segundos // 86400} días"


def mostrar_usuarios(origen):
    """Muestra los usuarios desde la base local. Nunca deja la pantalla vacía sin explicar."""
    filas = listar_usuarios()
    if not filas:
        print("\nNo hay datos guardados localmente todavía.")
        print("Conéctate a internet y ejecuta el programa de nuevo para descargarlos.")
        return

    print(f"\n=== Usuarios ({origen}) ===")
    for id_api, nombre, username, email, empresa, obtenido_en in filas:
        print(f"{id_api:>3} | {nombre:<25} | {username:<16} | {email}")
    print(f"\nDatos obtenidos de la API {antiguedad(filas[0][5])} "
          f"(obtenido_en = {filas[0][5]} UTC)")


def sincronizar():
    url = os.getenv("API_URL", URL_POR_DEFECTO)
    password_inicial = os.getenv("PASSWORD_INICIAL") or secrets.token_urlsafe(16)

    crear_tablas()
    origen = "datos locales (Plan B)"

    try:
        print(f"Consultando la API: {url}")
        datos = obtener_json(url)
        usuarios, rechazados = DeserializadorUsuarios().desde_lista(datos)
        for mensaje in rechazados:
            print(f"  [aviso] {mensaje}")
        insertados, actualizados = guardar_usuarios(usuarios, password_inicial)
        print(f"Sincronización lista: {insertados} nuevos, {actualizados} actualizados.")
        origen = "recién descargados de la API"
    except ApiClienteError as error:
        print(f"\n[ERROR de petición] {error}")
        print("Revisa la URL configurada. Se muestran los datos locales.")
    except ApiNoDisponibleError as error:
        print(f"\n[API no disponible] {error}")
        print("Se muestran los datos guardados localmente (Plan B).")
    except RespuestaInvalidaError as error:
        print(f"\n[Respuesta inválida] {error}")
        print("Se muestran los datos guardados localmente (Plan B).")
    except DatosInvalidosError as error:
        print(f"\n[Datos inválidos] {error}")
        print("Se muestran los datos guardados localmente (Plan B).")
    except ApiError as error:
        print(f"\n[Error de API] {error}")
        print("Se muestran los datos guardados localmente (Plan B).")
    except sqlite3.Error as error:
        print(f"\n[Error de base de datos] No se pudo guardar: {type(error).__name__}")
        print("Se muestran los datos que ya estaban guardados.")

    try:
        mostrar_usuarios(origen)
    except sqlite3.Error as error:
        print(f"\n[Error de base de datos] No se pudo leer: {type(error).__name__}")


def probar_login(username):
    clave = getpass.getpass(f"Contraseña de {username}: ")
    hash_guardado = obtener_hash(username)
    if hash_guardado and verificar_password(clave, hash_guardado):
        print("Inicio de sesión correcto.")
    else:
        print("Usuario o contraseña incorrectos.")


def main(argumentos):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    if len(argumentos) == 2 and argumentos[0] == "--login":
        crear_tablas()
        probar_login(argumentos[1])
    else:
        sincronizar()


if __name__ == "__main__":
    main(sys.argv[1:])
