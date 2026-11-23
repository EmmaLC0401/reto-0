# AGENTS.md

## Proyecto
Punto de Juego permite consultar canchas deportivas y reservar turnos de una hora.
Incluye registro, inicio/cierre de sesión, cancelación y prevención de reservas cruzadas.

## Stack
- Python 3.10+, Flask y plantillas Jinja.
- SQLite para usuarios, canchas y reservas; Werkzeug para hashes de contraseñas.
- CSS propio; dependencias de aplicación declaradas en `requirements.txt`.

## Comandos
```powershell
python -m pip install -r requirements.txt
$env:SECRET_KEY = (python -c "import secrets; print(secrets.token_hex(32))")
python app.py
python -m pytest -v
ruff check .
```
`pytest` y `ruff` no están declarados en `requirements.txt`; verifica su disponibilidad antes de usarlos.

## Estructura
- `app.py`: fábrica Flask, rutas, autenticación, SQLite y reservas.
- `requirements.txt`: dependencias de la aplicación.
- `README.md`: requisitos, ejecución y pruebas con unittest.
- `.gitignore`: entornos, secretos locales, bases de datos y cachés ignorados.
- `static/`: estilos CSS de la interfaz.
- `templates/`: páginas Jinja de reservas, autenticación y diseño común.
- `tests/`: pruebas de registro, inicio de sesión, CSRF y conflictos de reservas.
- `instance/`: base SQLite local creada automáticamente al iniciar la app.

## Qué no hacer
- No modificar las pruebas para que pasen.
- No escribir claves en el código.
- No instalar dependencias sin explicar para qué.
- No hacer commit ni push.

## Lecciones aprendidas
