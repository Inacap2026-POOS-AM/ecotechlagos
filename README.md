
# EcoTech Solutions – Evaluación Sumativa 3

**Asignatura:** Programación Orientada a Objeto Seguro (TI3021)  
**Carrera:** Analista Programador  
**Estudiante:** Matías Lagos  
**Institución:** INACAP

## Descripción del proyecto

EcoTech Solutions es un proyecto desarrollado en Python que busca incorporar funcionalidades de consumo de servicios externos, procesamiento de información, persistencia de datos y mecanismos básicos de seguridad.

Esta entrega corresponde a la tercera evaluación sumativa de la asignatura Programación Orientada a Objeto Seguro.

## Tecnologías utilizadas

- **Python:** lenguaje principal del proyecto.
- **Requests:** realización de solicitudes HTTP.
- **SQLite:** almacenamiento local de información.
- **Bcrypt:** protección de contraseñas mediante hashes.
- **Unittest:** desarrollo de pruebas automatizadas.
- **JSON:** intercambio y procesamiento de información.

## Estructura del proyecto

```text
ecotechlagos/
│
├── pruebas/
│   └── test_e3.py
│
├── .env.example
├── .gitignore
├── README.md
├── api_cliente.py
├── bitacora_ia.md
├── deserializador.py
├── main_e3.py
├── repositorio_usuarios.py
├── seguridad.py
├── requirements.txt
│
└── BITACORA_IA/
    └── bitacora.md
```

## Descripción de los módulos

| Archivo | Responsabilidad |
|---|---|
| `main_e3.py` | Punto de entrada y coordinación del programa. |
| `api_cliente.py` | Comunicación con servicios externos. |
| `deserializador.py` | Procesamiento y validación de información recibida. |
| `repositorio_usuarios.py` | Gestión de usuarios mediante SQLite. |
| `seguridad.py` | Funciones relacionadas con la protección de contraseñas. |
| `pruebas/test_e3.py` | Pruebas automatizadas del proyecto. |

## Instalación

1. Clonar el repositorio.
2. Instalar las dependencias:

```bash
pip install -r requirements.txt
```

3. Crear la configuración local a partir de `.env.example`.
4. Configurar las variables de entorno necesarias.
5. Ejecutar el programa:

```bash
python main_e3.py
```

## Seguridad

El proyecto incorpora mecanismos orientados a proteger la información y controlar los accesos:

- Hash de contraseñas mediante bcrypt.
- Validación de entradas.
- Consultas SQL parametrizadas.
- Manejo de excepciones.
- Control de tiempos de espera en solicitudes HTTP.
- Uso de variables de entorno para configuración sensible.

## Pruebas

El proyecto incluye pruebas automatizadas mediante `unittest`.

Para ejecutarlas:

```bash
python -m unittest discover -s pruebas -v
```

Los resultados deben verificarse en el entorno de ejecución antes de considerar las pruebas aprobadas.

## Documentación adicional

La carpeta `BITACORA_IA` contiene documentación sobre el uso de inteligencia artificial como herramienta de apoyo, las revisiones realizadas y las decisiones técnicas del desarrollo.

---

**Proyecto académico – INACAP**  
**EcoTech Solutions | TI3021**
