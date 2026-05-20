import sqlite3

from fastapi.testclient import TestClient

import app as survey_app


def test_survey_form_includes_optional_contact_fields():
    client = TestClient(survey_app.app)

    response = client.get("/")

    assert response.status_code == 200
    assert 'name="contact_email"' in response.text
    assert 'name="contact_wechat"' in response.text
    assert "邮箱号" in response.text
    assert "微信号" in response.text


def test_submit_stores_contact_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(survey_app, "DB_PATH", tmp_path / "survey.db")
    survey_app.init_db()
    client = TestClient(survey_app.app)

    response = client.post(
        "/submit",
        data={
            "contact_email": "participant@example.org",
            "contact_wechat": "green-force-2026",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    conn = sqlite3.connect(tmp_path / "survey.db")
    row = conn.execute(
        "SELECT contact_email, contact_wechat FROM responses"
    ).fetchone()
    conn.close()

    assert row == ("participant@example.org", "green-force-2026")


def test_init_db_adds_contact_columns_to_existing_database(tmp_path, monkeypatch):
    db_path = tmp_path / "survey.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT DEFAULT (datetime('now','localtime')),
            q1_org_name TEXT DEFAULT ''
        );
        """
    )
    conn.close()

    monkeypatch.setattr(survey_app, "DB_PATH", db_path)
    survey_app.init_db()

    conn = sqlite3.connect(db_path)
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(responses)").fetchall()
    }
    conn.close()

    assert "contact_email" in columns
    assert "contact_wechat" in columns
