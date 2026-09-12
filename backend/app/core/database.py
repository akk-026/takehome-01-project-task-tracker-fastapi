from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


database_url = settings.database_url
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+psycopg://", 1)
elif database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

engine_options = {"connect_args": {"check_same_thread": False}} if database_url.startswith("sqlite") else {"pool_pre_ping": True}
engine = create_engine(database_url, **engine_options)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def initialise_database() -> None:
    # Models are imported here so future feature commits register their tables before creation.
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate_legacy_tasks()
    _backfill_legacy_task_history()


def _migrate_legacy_tasks() -> None:
    """Keep the local SQLite demo database compatible as task fields are introduced."""
    if engine.dialect.name != "sqlite" or "tasks" not in inspect(engine).get_table_names():
        return
    columns = {column["name"] for column in inspect(engine).get_columns("tasks")}
    additions = {
        "description": "VARCHAR(4000) NOT NULL DEFAULT ''",
        "priority": "VARCHAR(8) NOT NULL DEFAULT 'MEDIUM'",
        "due_date": "DATE",
        "status": "VARCHAR(15) NOT NULL DEFAULT 'BACKLOG'",
        "blocked_from": "VARCHAR(15)",
        "updated_at": "DATETIME",
        "completed_at": "DATETIME",
    }
    with engine.begin() as connection:
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(text(f"ALTER TABLE tasks ADD COLUMN {name} {definition}"))
        if "updated_at" not in columns:
            connection.execute(text("UPDATE tasks SET updated_at = created_at WHERE updated_at IS NULL"))
        if "completed_at" not in columns:
            connection.execute(text("UPDATE tasks SET completed_at = updated_at WHERE status = 'DONE'"))


def _backfill_legacy_task_history() -> None:
    """Give pre-history tasks an honest creation marker without inventing an actor."""
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO task_activities (task_id, actor_id, action, created_at)
                SELECT tasks.id, NULL, 'CREATED', tasks.created_at
                FROM tasks
                WHERE NOT EXISTS (
                    SELECT 1 FROM task_activities WHERE task_activities.task_id = tasks.id
                )
                """
            )
        )
