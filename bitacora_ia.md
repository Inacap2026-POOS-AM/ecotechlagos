# Bitácora de uso crítico de IA — Entrega 3 (TI3021)

**Herramienta:** Claude (Anthropic), modelo Claude Sonnet 5.5
**Fecha de consulta:** 20 de noviembre de 2026
**Propósito:** generar un borrador del script de consumo seguro de APIs (cliente HTTP con reintentos, Plan B con base local, deserializador, hash de contraseñas) sobre el proyecto EcoTech de la Etapa II.

**Declaración de autoría:** el código fue generado preliminarmente por IA. Yo lo ejecuté, lo audité contra las 5 señales de riesgo y puedo explicar cada decisión en la defensa. Las pruebas automáticas están en `pruebas/test_e3.py`.

---

## Auditoría de las 5 señales de riesgo

| # | Señal de riesgo | Qué suele sugerir una IA | Decisión | Justificación técnica y evidencia |
|---|---|---|---|---|
| 1 | **f-strings / concatenación en SQL** | `conn.execute(f"SELECT ... WHERE username = '{username}'")` | **Descarto** | Armar SQL con texto del usuario permite inyección (`' OR '1'='1`). Todas las consultas son literales completos con `?` y los valores viajan aparte (`SQL_INSERTAR`, `SQL_ACTUALIZAR`, `SQL_OBTENER_HASH` en `repositorio_usuarios.py`). Evidencia: `test_sin_sql_armado_con_texto_dinamico` (revisa el código con `ast`) y `test_inyeccion_sql_en_obtener_hash`. |
| 2 | **`verify=False`** | Desactivar la verificación SSL "para que deje de fallar" ante un error de certificado. | **Descarto** | Sin verificación, cualquiera en la red puede suplantar al servidor (ataque man-in-the-middle). No aparece en el código; si hay un error SSL se trata como falla de conexión. Evidencia: `test_sin_verify_false`. |
| 3 | **`except: pass`** | `try: ... except: pass` para que "nunca se caiga". | **Descarto** (modifico) | Oculta fallas y deja el sistema en estado desconocido. Cada bloque captura excepciones específicas (`requests.exceptions.Timeout`, `ConnectionError`, `sqlite3.Error`, `ApiError` y sus subclases) y muestra un mensaje claro. Única excepción: `except ImportError: pass` al cargar `python-dotenv`, que es opcional; es intencional y acotado. Evidencia: `test_sin_except_generico`. |
| 4 | **Llamadas sin `timeout`** | `requests.get(url)` a secas. | **Modifico** | Sin timeout, `requests` puede esperar indefinidamente y congelar el programa. Se fijó `TIMEOUT = (3.05, 10)` (conexión, lectura) y se pasa en cada llamada. Evidencia: `test_toda_llamada_requests_lleva_timeout` y `test_exito_envia_timeout`. |
| 5 | **Librerías inexistentes en PyPI** | Importar paquetes inventados (por ejemplo, un `requests-retry-helper` que no existe). | **Acepto, tras verificar** | Solo se usan 3 paquetes: `requests`, `bcrypt` y `python-dotenv`. Los reintentos y el backoff se escribieron a mano, sin paquetes extra. Verificación manual en pypi.org: ver lista de abajo. |

**Verificación de librerías (marcar al hacerla):**
- [ ] `requests` existe en https://pypi.org/project/requests/
- [ ] `bcrypt` existe en https://pypi.org/project/bcrypt/
- [ ] `python-dotenv` existe en https://pypi.org/project/python-dotenv/
- [ ] `pip install -r requirements.txt` terminó sin errores en mi equipo

---

## Otros fragmentos auditados

| Fragmento | Aspecto | Decisión | Justificación |
|---|---|---|---|
| Reintentar siempre ante cualquier error HTTP | Resiliencia | **Modifico** | Reintentar un 404 es inútil. Los 4xx no se reintentan (`ApiClienteError`); el 429 espera lo que indica `Retry-After`; los 5xx y las fallas de red sí se reintentan, máximo 4 intentos con espera 1 s, 2 s, 4 s. Evidencia: `test_4xx_no_reintenta`, `test_429_respeta_retry_after`, `test_5xx_reintenta_con_backoff_exponencial`. |
| Guardar el JSON de la API directo en la base | Validación | **Modifico** | Un dato malformado podría llegar a la base. `DeserializadorUsuarios` valida tipos, email e id, y descarta solo el registro malo sin tumbar al resto. |
| `INSERT` simple en cada ejecución | Idempotencia | **Modifico** | Duplicaba usuarios al correr dos veces. Se consulta si existe: si no, se inserta; si sí, se actualiza. Todo en una sola transacción. Evidencia: `test_idempotencia`. |
| Recalcular el hash en cada ejecución | Seguridad / datos | **Modifico** | Cambiar las contraseñas en cada corrida es un error. El `UPDATE` no toca `password_hash`. Evidencia: `test_segunda_ejecucion_no_cambia_el_hash`. |
| Contraseña guardada tal cual o con hash sin salt | Seguridad | **Descarto** | Se usa `bcrypt`, que genera un salt aleatorio por contraseña. Cada hash es distinto aunque la clave sea igual. Evidencia: `test_sin_contrasenas_en_texto_plano`. También se valida el límite de 72 bytes de bcrypt. |
| Pantalla vacía o traza de error si no hay red | Degradación controlada | **Modifico** | Ante cualquier falla de la API se muestran los datos locales con su antigüedad (`obtenido_en`); si tampoco hay datos locales, un mensaje explicativo. |

---

## Qué ejecuté para comprobarlo
- [ ] `python -m unittest discover -s pruebas -t . -v` → todas las pruebas en OK
- [ ] `python main_e3.py` dos veces → la segunda dice "0 nuevos, N actualizados"
- [ ] Apagué el WiFi y ejecuté de nuevo → muestra datos locales con `obtenido_en`
- [ ] Cambié `API_URL` en `.env` a una dirección inexistente → mensaje de error sin reintentos
- [ ] Revisé la tabla `usuario` → la columna `password_hash` solo tiene hashes `$2b$...`
