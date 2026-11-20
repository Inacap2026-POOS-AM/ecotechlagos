"""Hash de contraseñas con bcrypt (incluye salt aleatorio automático)."""
import bcrypt

MAX_BYTES_BCRYPT = 72  # bcrypt solo usa los primeros 72 bytes


def hashear_password(password):
    """Devuelve el hash bcrypt (texto). Cada llamada genera un salt distinto."""
    if not isinstance(password, str) or not password:
        raise ValueError("La contraseña no puede estar vacía")
    datos = password.encode("utf-8")
    if len(datos) > MAX_BYTES_BCRYPT:
        raise ValueError("La contraseña no puede superar 72 bytes")
    return bcrypt.hashpw(datos, bcrypt.gensalt()).decode("utf-8")


def verificar_password(password, hash_guardado):
    """True si la contraseña coincide con el hash guardado."""
    if not isinstance(password, str) or not hash_guardado:
        return False
    datos = password.encode("utf-8")
    if len(datos) > MAX_BYTES_BCRYPT:
        return False
    try:
        return bcrypt.checkpw(datos, hash_guardado.encode("utf-8"))
    except ValueError:
        # hash corrupto o con formato inválido
        return False
