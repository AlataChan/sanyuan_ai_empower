from pathlib import Path

import app as survey_app


def test_resolve_db_path_uses_explicit_env_path(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    env_db = tmp_path / "custom" / "responses.db"

    db_path = survey_app.resolve_db_path(
        base=tmp_path / "app",
        data_dir=data_dir,
        env={"SURVEY_DB_PATH": str(env_db)},
    )

    assert db_path == env_db


def test_resolve_db_path_uses_data_volume_when_present(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()

    db_path = survey_app.resolve_db_path(
        base=tmp_path / "app",
        data_dir=data_dir,
        env={},
    )

    assert db_path == data_dir / "survey.db"


def test_resolve_db_path_falls_back_to_project_database(tmp_path):
    base = tmp_path / "app"

    db_path = survey_app.resolve_db_path(
        base=base,
        data_dir=tmp_path / "missing-data",
        env={},
    )

    assert db_path == Path(base) / "survey.db"
