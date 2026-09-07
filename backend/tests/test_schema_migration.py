"""Additive schema migration.

Without this, adding a column to a model leaves the live table behind and
the next insert fails at runtime - the failure surfaces during a trace, not
at startup, which is the worst possible time to discover it.
"""
from sqlalchemy import Column, Float, Integer, MetaData, String, Table, create_engine, inspect, text

from app.db import postgres as pg


def _engine_with_old_table(tmp_path):
    """A database whose table predates a column added to the model."""
    engine = create_engine(f"sqlite:///{tmp_path}/legacy.db")
    old = MetaData()
    Table("widgets", old,
          Column("id", Integer, primary_key=True),
          Column("name", String))
    old.create_all(engine)
    return engine


def test_missing_column_is_added(tmp_path, monkeypatch):
    engine = _engine_with_old_table(tmp_path)

    # The model has since gained a column the live table lacks.
    new = MetaData()
    Table("widgets", new,
          Column("id", Integer, primary_key=True),
          Column("name", String),
          Column("score", Float, default=0.0))

    monkeypatch.setattr(pg, "engine", engine)
    monkeypatch.setattr(pg.Base, "metadata", new)
    pg.ensure_additive_schema()

    columns = {c["name"] for c in inspect(engine).get_columns("widgets")}
    assert "score" in columns


def test_existing_data_survives_the_added_column(tmp_path, monkeypatch):
    """An added column must not cost the rows already in the table - that is
    the whole reason not to drop and recreate."""
    engine = _engine_with_old_table(tmp_path)
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO widgets (name) VALUES ('existing case')"))

    new = MetaData()
    Table("widgets", new,
          Column("id", Integer, primary_key=True),
          Column("name", String),
          Column("score", Float, default=0.0))
    monkeypatch.setattr(pg, "engine", engine)
    monkeypatch.setattr(pg.Base, "metadata", new)
    pg.ensure_additive_schema()

    with engine.begin() as conn:
        rows = conn.execute(text("SELECT name FROM widgets")).fetchall()
    assert [r[0] for r in rows] == ["existing case"]


def test_running_twice_is_a_no_op(tmp_path, monkeypatch):
    engine = _engine_with_old_table(tmp_path)
    new = MetaData()
    Table("widgets", new,
          Column("id", Integer, primary_key=True),
          Column("name", String),
          Column("score", Float, default=0.0))
    monkeypatch.setattr(pg, "engine", engine)
    monkeypatch.setattr(pg.Base, "metadata", new)

    pg.ensure_additive_schema()
    pg.ensure_additive_schema()  # must not raise on the second pass

    columns = [c["name"] for c in inspect(engine).get_columns("widgets")]
    assert columns.count("score") == 1


def test_unknown_table_is_left_alone(tmp_path, monkeypatch):
    """Tables that do not exist yet belong to create_all, not to this."""
    engine = create_engine(f"sqlite:///{tmp_path}/empty.db")
    new = MetaData()
    Table("not_created_yet", new, Column("id", Integer, primary_key=True))
    monkeypatch.setattr(pg, "engine", engine)
    monkeypatch.setattr(pg.Base, "metadata", new)

    pg.ensure_additive_schema()  # no crash

    assert "not_created_yet" not in inspect(engine).get_table_names()
