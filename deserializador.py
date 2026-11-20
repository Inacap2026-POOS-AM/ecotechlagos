"""Deserializador propio: valida y convierte el JSON de la API en objetos."""
import re
from dataclasses import dataclass

PATRON_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class DatosInvalidosError(ValueError):
    """Un registro del JSON no cumple el formato esperado."""


@dataclass(frozen=True)
class UsuarioAPI:
    id_api: int
    nombre: str
    username: str
    email: str
    telefono: str
    sitio_web: str
    empresa: str


class DeserializadorUsuarios:
    """Convierte cada diccionario del JSON en un UsuarioAPI validado."""

    @staticmethod
    def _texto_obligatorio(dato, campo):
        valor = dato.get(campo)
        if not isinstance(valor, str) or not valor.strip():
            raise DatosInvalidosError(f"Campo '{campo}' ausente o vacío")
        return valor.strip()

    @staticmethod
    def _texto_opcional(valor):
        return valor.strip() if isinstance(valor, str) else ""

    def desde_dict(self, dato):
        """Valida UN registro. Lanza DatosInvalidosError si algo no calza."""
        if not isinstance(dato, dict):
            raise DatosInvalidosError("El registro no es un objeto JSON")

        id_api = dato.get("id")
        if isinstance(id_api, bool) or not isinstance(id_api, int) or id_api <= 0:
            raise DatosInvalidosError("Campo 'id' debe ser un entero positivo")

        email = self._texto_obligatorio(dato, "email")
        if not PATRON_EMAIL.match(email):
            raise DatosInvalidosError(f"Email con formato inválido: {email}")

        empresa = dato.get("company")
        nombre_empresa = self._texto_opcional(empresa.get("name")) if isinstance(empresa, dict) else ""

        return UsuarioAPI(
            id_api=id_api,
            nombre=self._texto_obligatorio(dato, "name"),
            username=self._texto_obligatorio(dato, "username"),
            email=email.lower(),
            telefono=self._texto_opcional(dato.get("phone")),
            sitio_web=self._texto_opcional(dato.get("website")),
            empresa=nombre_empresa,
        )

    def desde_lista(self, datos):
        """Valida una lista completa.

        Devuelve (usuarios_validos, mensajes_de_rechazo). Un registro malo
        no tumba al resto: se descarta y se informa.
        """
        if not isinstance(datos, list):
            raise DatosInvalidosError("Se esperaba una lista de usuarios en el JSON")

        validos, rechazados = [], []
        for posicion, dato in enumerate(datos):
            try:
                validos.append(self.desde_dict(dato))
            except DatosInvalidosError as error:
                rechazados.append(f"Registro #{posicion}: {error}")
        return validos, rechazados
