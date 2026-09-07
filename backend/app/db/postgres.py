import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

logger = logging.getLogger(__name__)

db_url = get_settings().database_url
connect_args = {"check_same_thread": False} if db_url.startswith("sqlite") else {}
engine = create_engine(db_url, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_additive_schema() -> None:
    """Add columns that exist in the models but not yet in the database.

    `create_all()` creates missing tables but never alters existing ones, so
    adding a column to a model silently leaves the live table behind and the
    next insert fails. Without migrations that means "reset the database"
    after every model change, which is fine on day one and unacceptable once
    there are cases worth keeping.

    Deliberately additive only. Adding a nullable column is safe and
    reversible; renames, drops and type changes are not, and quietly guessing
    at them is how a migration tool destroys data. Anything beyond an added
    column still needs a real migration - this closes the common case, it is
    not Alembic.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table in Base.metadata.sorted_tables:
        if table.name not in existing_tables:
            continue  # create_all handles brand-new tables
        live_columns = {c["name"] for c in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in live_columns:
                continue
            column_type = column.type.compile(dialect=engine.dialect)
            default = ""
            if column.default is not None and getattr(column.default, "is_scalar", False):
                literal = column.default.arg
                default = f" DEFAULT {literal!r}" if isinstance(literal, str) else f" DEFAULT {literal}"
            try:
                with engine.begin() as conn:
                    conn.execute(text(
                        f"ALTER TABLE {table.name} ADD COLUMN {column.name} {column_type}{default}"
                    ))
                logger.info(f"Added missing column {table.name}.{column.name}")
            except Exception as e:  # noqa: BLE001 - startup must not die on this
                logger.warning(f"Could not add {table.name}.{column.name}: {e}")
