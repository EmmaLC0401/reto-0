import tempfile
import unittest
from pathlib import Path

from app import create_app, get_db


class BookingAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "DATABASE": str(Path(self.temp_dir.name) / "test.sqlite3"),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def csrf_token(self):
        self.client.get("/")
        with self.client.session_transaction() as session:
            return session["_csrf_token"]

    def register(self, username):
        return self.client.post(
            "/registro",
            data={
                "csrf_token": self.csrf_token(),
                "username": username,
                "password": "secure-pass-123",
            },
            follow_redirects=True,
        )

    def book(self, court_id, hour, day):
        return self.client.post(
            "/reservas",
            data={
                "csrf_token": self.csrf_token(),
                "court_id": court_id,
                "date": day,
                "hour": hour,
            },
            follow_redirects=True,
        )

    def test_registration_login_and_hourly_booking(self):
        response = self.register("jugador1")
        self.assertIn("Tu cuenta está lista".encode(), response.data)

        day = "2099-06-15"
        response = self.book(1, 10, day)
        self.assertIn("¡Cancha reservada!".encode(), response.data)

        self.client.post(
            "/cerrar-sesion",
            data={"csrf_token": self.csrf_token()},
            follow_redirects=True,
        )
        response = self.client.post(
            "/iniciar-sesion",
            data={
                "csrf_token": self.csrf_token(),
                "username": "jugador1",
                "password": "secure-pass-123",
            },
            follow_redirects=True,
        )
        self.assertIn("Fútbol 5".encode(), response.data)

    def test_overlapping_reservation_is_rejected_but_other_court_is_available(self):
        day = "2099-06-15"
        self.register("jugador1")
        first = self.book(1, 10, day)
        self.assertIn("¡Cancha reservada!".encode(), first.data)

        self.client.post(
            "/cerrar-sesion",
            data={"csrf_token": self.csrf_token()},
            follow_redirects=True,
        )
        self.register("jugador2")
        conflict = self.book(1, 10, day)
        self.assertIn("Ese horario acaba de ocuparse".encode(), conflict.data)

        available = self.book(2, 10, day)
        self.assertIn("¡Cancha reservada!".encode(), available.data)

    def test_post_without_csrf_token_is_rejected(self):
        response = self.client.post("/registro", data={"username": "jugador1"})
        self.assertEqual(response.status_code, 400)

    def test_initializing_again_does_not_duplicate_courts(self):
        create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-secret",
                "DATABASE": str(Path(self.temp_dir.name) / "test.sqlite3"),
            }
        )
        with self.app.app_context():
            count = get_db().execute("SELECT COUNT(*) FROM courts").fetchone()[0]
        self.assertEqual(count, 3)


if __name__ == "__main__":
    unittest.main()
