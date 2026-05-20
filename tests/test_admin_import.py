import io
import sqlite3

from fastapi.testclient import TestClient

import app as survey_app


def test_admin_dashboard_includes_csv_import_form(tmp_path, monkeypatch):
    monkeypatch.setattr(survey_app, "DB_PATH", tmp_path / "survey.db")
    survey_app.init_db()
    client = TestClient(survey_app.app)

    response = client.get(
        "/admin/dashboard",
        cookies={survey_app.ADMIN_COOKIE: survey_app.ADMIN_PASSWORD_HASH},
    )

    assert response.status_code == 200
    assert 'action="/admin/import"' in response.text
    assert 'name="csv_file"' in response.text
    assert "导入 CSV" in response.text


def test_admin_import_restores_exported_csv_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(survey_app, "DB_PATH", tmp_path / "survey.db")
    survey_app.init_db()
    csv_content = (
        "id,created_at,contact_email,contact_wechat,q1_org_name\n"
        "1,2026-05-20 10:00:00,old@example.org,old-wechat,旧回复机构\n"
    )
    client = TestClient(survey_app.app)

    response = client.post(
        "/admin/import",
        files={"csv_file": ("survey_export.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")},
        cookies={survey_app.ADMIN_COOKIE: survey_app.ADMIN_PASSWORD_HASH},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/dashboard?imported=1"

    conn = sqlite3.connect(tmp_path / "survey.db")
    row = conn.execute(
        "SELECT id, created_at, contact_email, contact_wechat, q1_org_name FROM responses"
    ).fetchone()
    conn.close()

    assert row == (
        1,
        "2026-05-20 10:00:00",
        "old@example.org",
        "old-wechat",
        "旧回复机构",
    )
