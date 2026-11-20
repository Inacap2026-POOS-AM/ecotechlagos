"""Cliente HTTP resiliente para consumir APIs de forma segura.

Reglas que implementa (Entrega 3):
  * Todas las peticiones llevan timeout explícito.
  * 4xx  -> error del cliente: NO se reintenta (excepto 429).
  * 429  -> se espera lo que indique la cabecera Retry-After y se reintenta.
  * 5xx y fallas de red/timeout -> se reintenta con backoff exponencial.
  * Máximo MAX_INTENTOS intentos en total.
  * Nunca se desactiva la verificación SSL (verify=False está prohibido).
"""
import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

logger = logging.getLogger(__name__)

# (segundos para conectar, segundos para recibir respuesta)
TIMEOUT = (3.05, 10)
MAX_INTENTOS = 4
ESPERA_BASE = 1          # segundos: 1, 2, 4, ...
ESPERA_MAXIMA = 30       # tope para cualquier espera (incluye Retry-After)


class ApiError(Exception):
    """Error base de todo lo que pueda fallar al consumir la API."""


class ApiClienteError(ApiError):
    """Respuesta 4xx (o URL mal formada): el problema es la petición, no el servidor."""

    def __init__(self, mensaje, status=None):
        super().__init__(mensaje)
        self.status = status


class ApiNoDisponibleError(ApiError):
    """La API no respondió bien tras agotar los reintentos (5xx, red o timeout)."""


class RespuestaInvalidaError(ApiError):
    """La API respondió 200 pero el cuerpo no es JSON válido."""


def _espera_retry_after(valor, intento):
    """Convierte la cabecera Retry-After (segundos o fecha HTTP) en segundos de espera."""
    if valor:
        try:
            segundos = float(valor)
        except ValueError:
            try:
                fecha = parsedate_to_datetime(valor)
                segundos = (fecha - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError):
                segundos = None
        if segundos is not None:
            return max(0, min(segundos, ESPERA_MAXIMA))
    return min(ESPERA_BASE * 2 ** (intento - 1), ESPERA_MAXIMA)


def _espera_backoff(intento):
    """Espera exponencial: 1s, 2s, 4s, ... con tope."""
    return min(ESPERA_BASE * 2 ** (intento - 1), ESPERA_MAXIMA)


def obtener_json(url, max_intentos=MAX_INTENTOS, dormir=time.sleep):
    """GET a `url` y devuelve el JSON ya convertido a objetos de Python.

    `dormir` se puede reemplazar en las pruebas para no esperar de verdad.
    Lanza ApiClienteError, ApiNoDisponibleError o RespuestaInvalidaError.
    """
    ultimo_motivo = "sin detalle"

    for intento in range(1, max_intentos + 1):
        espera = None
        try:
            respuesta = requests.get(url, timeout=TIMEOUT)
        except (requests.exceptions.MissingSchema,
                requests.exceptions.InvalidSchema,
                requests.exceptions.InvalidURL) as error:
            # URL mal escrita: reintentar no sirve de nada.
            raise ApiClienteError(f"URL inválida: {url}") from error
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as error:
            ultimo_motivo = f"sin conexión o tiempo agotado ({type(error).__name__})"
            espera = _espera_backoff(intento)
        except requests.exceptions.RequestException as error:
            ultimo_motivo = f"error de red ({type(error).__name__})"
            espera = _espera_backoff(intento)
        else:
            codigo = respuesta.status_code

            if 200 <= codigo < 300:
                try:
                    return respuesta.json()
                except ValueError as error:
                    raise RespuestaInvalidaError(
                        "La API respondió, pero el contenido no es JSON válido") from error

            if codigo == 429:
                ultimo_motivo = "HTTP 429 (demasiadas peticiones)"
                espera = _espera_retry_after(respuesta.headers.get("Retry-After"), intento)
            elif 400 <= codigo < 500:
                # 4xx: no se reintenta.
                raise ApiClienteError(
                    f"La API rechazó la petición (HTTP {codigo}). No se reintenta.",
                    status=codigo)
            elif codigo >= 500:
                ultimo_motivo = f"HTTP {codigo} (falla del servidor)"
                espera = _espera_backoff(intento)
            else:
                # 3xx sin seguir u otros códigos raros: se tratan como fallo no reintentable.
                raise ApiClienteError(f"Respuesta inesperada (HTTP {codigo})", status=codigo)

        if intento < max_intentos:
            logger.warning("Intento %d/%d falló: %s. Reintentando en %.1f s...",
                           intento, max_intentos, ultimo_motivo, espera)
            dormir(espera)
        else:
            logger.warning("Intento %d/%d falló: %s.", intento, max_intentos, ultimo_motivo)

    raise ApiNoDisponibleError(
        f"La API no está disponible tras {max_intentos} intentos ({ultimo_motivo})")
