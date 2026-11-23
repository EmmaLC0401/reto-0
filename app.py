import os
import secrets
import sqlite3
from datetime import date, datetime, time, timedelta
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

HOUR_SLOTS = range(8, 22)
COURTS = (
    ("Fútbol 5", "Fútbol"),
    ("Pádel Norte", "Pádel"),
    ("Tenis Central", "Tenis"),
)


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=str(Path(app.instance_path) / "reservas.sqlite3"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    init_db(app)

    @app.before_request
    def protect_post_requests():
        if request.method == "POST":
            token = request.form.get("csrf_token", "")
            if not token or not secrets.compare_digest(
                token, session.get("_csrf_token", "")
            ):
                abort(400, description="La sesión del formulario expiró. Inténtalo otra vez.")

    @app.context_processor
    def add_template_helpers():
        def csrf_token():
            if "_csrf_token" not in session:
                session["_csrf_token"] = secrets.token_urlsafe(32)
            return session["_csrf_token"]

        return {"csrf_token": csrf_token}

    @app.before_request
    def load_user():
        user_id = session.get("user_id")
        g.user = None
        if user_id is not None:
            connection = get_db()
            g.user = connection.execute(
                "SELECT id, username FROM users WHERE id = ?", (user_id,)
            ).fetchone()
            if g.user is None:
                session.pop("user_id", None)

    @app.teardown_appcontext
    def close_db(error=None):
        connection = g.pop("db", None)
        if connection is not None:
            connection.close()

    def login_required(view):
        @wraps(view)
        def wrapped_view(**kwargs):
            if g.user is None:
                flash("Inicia sesión para reservar una cancha.", "info")
                return redirect(url_for("login"))
            return view(**kwargs)

        return wrapped_view

    @app.get("/")
    def index():
        try:
            selected_day = date.fromisoformat(request.args.get("date", ""))
        except ValueError:
            selected_day = date.today()
        selected_day = max(selected_day, date.today())

        reservations = get_db().execute(
            """
            SELECT r.id, r.court_id, r.user_id, r.starts_at, r.ends_at,
                   c.name AS court_name, c.sport
            FROM reservations AS r
            JOIN courts AS c ON c.id = r.court_id
            WHERE r.starts_at < ? AND r.ends_at > ?
            ORDER BY r.starts_at
            """,
            (
                datetime.combine(selected_day + timedelta(days=1), time.min).isoformat(),
                datetime.combine(selected_day, time.min).isoformat(),
            ),
        ).fetchall()
        occupied = {
            (row["court_id"], datetime.fromisoformat(row["starts_at"]).hour)
            for row in reservations
        }
        courts = get_db().execute("SELECT id, name, sport FROM courts ORDER BY id").fetchall()
        return render_template(
            "index.html",
            courts=courts,
            reservations=reservations,
            occupied=occupied,
            selected_day=selected_day,
            min_date=date.today().isoformat(),
            slots=HOUR_SLOTS,
        )

    @app.route("/registro", methods=["GET", "POST"])
    def register():
        if g.user is not None:
            return redirect(url_for("index"))
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            if not 3 <= len(username) <= 40 or len(password) < 8:
                flash("El usuario debe tener entre 3 y 40 caracteres y la contraseña al menos 8.", "error")
            else:
                try:
                    connection = get_db()
                    connection.execute(
                        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                        (username, generate_password_hash(password)),
                    )
                    connection.commit()
                except sqlite3.IntegrityError:
                    flash("Ese nombre de usuario ya está registrado.", "error")
                else:
                    session.clear()
                    session["user_id"] = connection.execute(
                        "SELECT id FROM users WHERE username = ?", (username,)
                    ).fetchone()["id"]
                    flash("Tu cuenta está lista. ¡A jugar!", "success")
                    return redirect(url_for("index"))
        return render_template("auth.html", mode="register")

    @app.route("/iniciar-sesion", methods=["GET", "POST"])
    def login():
        if g.user is not None:
            return redirect(url_for("index"))
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = get_db().execute(
                "SELECT id, password_hash FROM users WHERE username = ?", (username,)
            ).fetchone()
            if user is None or not check_password_hash(user["password_hash"], password):
                flash("Usuario o contraseña incorrectos.", "error")
            else:
                session.clear()
                session["user_id"] = user["id"]
                flash("Has iniciado sesión.", "success")
                return redirect(url_for("index"))
        return render_template("auth.html", mode="login")

    @app.post("/cerrar-sesion")
    @login_required
    def logout():
        session.clear()
        flash("Has cerrado sesión.", "info")
        return redirect(url_for("index"))

    @app.post("/reservas")
    @login_required
    def book():
        try:
            court_id = int(request.form.get("court_id", ""))
            selected_day = date.fromisoformat(request.form.get("date", ""))
            hour = int(request.form.get("hour", ""))
        except ValueError:
            abort(400, description="La cancha, la fecha o la hora no son válidas.")

        if hour not in HOUR_SLOTS or selected_day < date.today():
            abort(400, description="Elige un horario disponible desde hoy.")

        starts_at = datetime.combine(selected_day, time(hour)).isoformat()
        ends_at = (datetime.combine(selected_day, time(hour)) + timedelta(hours=1)).isoformat()
        connection = get_db()
        try:
            connection.execute("BEGIN IMMEDIATE")
            court = connection.execute(
                "SELECT id FROM courts WHERE id = ?", (court_id,)
            ).fetchone()
            if court is None:
                connection.rollback()
                abort(404)
            conflict = connection.execute(
                """
                SELECT 1 FROM reservations
                WHERE court_id = ? AND starts_at < ? AND ends_at > ?
                LIMIT 1
                """,
                (court_id, ends_at, starts_at),
            ).fetchone()
            if conflict:
                connection.rollback()
                flash("Ese horario acaba de ocuparse. Elige otro.", "error")
            else:
                connection.execute(
                    """
                    INSERT INTO reservations (court_id, user_id, starts_at, ends_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (court_id, g.user["id"], starts_at, ends_at),
                )
                connection.commit()
                flash("¡Cancha reservada! Te esperamos.", "success")
        except sqlite3.Error:
            connection.rollback()
            raise
        return redirect(url_for("index", date=selected_day.isoformat()))

    @app.post("/reservas/<int:reservation_id>/cancelar")
    @login_required
    def cancel_booking(reservation_id):
        connection = get_db()
        cursor = connection.execute(
            "DELETE FROM reservations WHERE id = ? AND user_id = ?",
            (reservation_id, g.user["id"]),
        )
        connection.commit()
        if cursor.rowcount == 0:
            abort(404)
        flash("Tu reserva ha sido cancelada.", "info")
        return redirect(url_for("index"))

    return app


def get_db():
    if "db" not in g:
        connection = sqlite3.connect(
            current_app.config["DATABASE"], timeout=10, isolation_level=None
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        g.db = connection
    return g.db


def init_db(app):
    connection = sqlite3.connect(app.config["DATABASE"])
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL COLLATE NOCASE UNIQUE,
            password_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS courts (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            sport TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY,
            court_id INTEGER NOT NULL REFERENCES courts(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            starts_at TEXT NOT NULL,
            ends_at TEXT NOT NULL,
            CHECK (starts_at < ends_at)
        );
        CREATE INDEX IF NOT EXISTS reservations_court_time
            ON reservations (court_id, starts_at, ends_at);
        """
    )
    connection.executemany(
        """
        INSERT INTO courts (name, sport)
        SELECT ?, ? WHERE NOT EXISTS (
            SELECT 1 FROM courts WHERE name = ?
        )
        """,
        ((name, sport, name) for name, sport in COURTS),
    )
    connection.commit()
    connection.close()


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1")
