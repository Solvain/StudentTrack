from app.db import database_url


def test_database_url_reads_connection_settings_without_reinterpreting_password(monkeypatch):
    settings = {
        "POSTGRES_HOST": "database.internal",
        "POSTGRES_PORT": "5544",
        "POSTGRES_DB": "studenttrack_test",
        "POSTGRES_USER": "student",
        "POSTGRES_PASSWORD": "local@:/%password",
    }
    for name, value in settings.items():
        monkeypatch.setenv(name, value)

    url = database_url()

    assert url.drivername == "postgresql+psycopg"
    assert url.host == "database.internal"
    assert url.port == 5544
    assert url.database == "studenttrack_test"
    assert url.username == "student"
    assert url.password == settings["POSTGRES_PASSWORD"]
