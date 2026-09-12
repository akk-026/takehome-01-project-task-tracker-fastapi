from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


engine_options = {"connect_args": {"check_same_thread": False}} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def initialise_database() -> None:
    # Models are imported here so future feature commits register their tables before creation.
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_legacy_tasks()


def _migrate_legacy_tasks() -> None:
    """Keep the local SQLite demo database compatible as task fields are introduced."""
    if engine.dialect.name != "sqlite" or "tasks" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("tasks")}
    additions = {
        "description": "VARCHAR(4000) NOT NULL DEFAULT ''",
        "priority": "VARCHAR(8) NOT NULL DEFAULT 'MEDIUM'",
        "due_date": "DATE",
        "updated_at": "DATETIME",
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE tasks ADD COLUMN {name} {definition}"))
        if "updated_at" not in columns:
            connection.execute(text("UPDATE tasks SET updated_at = created_at WHERE updated_at IS NULL"))
