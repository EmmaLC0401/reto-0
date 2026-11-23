# Punto de Juego

Aplicación web en Flask para consultar canchas deportivas y reservar turnos de una hora.

## Requisitos

- Python 3.10 o posterior
- Flask (consulta `requirements.txt`)

## Ejecutar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:SECRET_KEY = "reemplaza-por-una-clave-aleatoria-larga"
python app.py
```

Abre http://127.0.0.1:5000. La base SQLite se crea automáticamente en `instance\reservas.sqlite3` con canchas de fútbol, pádel y tenis. Para producción, configura una clave secreta segura y ejecuta Flask detrás de un servidor WSGI.

## Pruebas

```powershell
python -m unittest discover -s tests
```
