"""Direct Alembic environment; no ASGI application or request context needed."""
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from app.config import Settings
from app.database import Base, make_engine
from app import models  # noqa: F401 - register all mapped tables

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)
settings = config.attributes.get("settings") or Settings()
target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(url=settings.DATABASE_URL, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    supplied = config.attributes.get("connection")
    if supplied is not None:
        context.configure(connection=supplied, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
        return
    Path(settings.INSTANCE_PATH).mkdir(parents=True, exist_ok=True)
    engine = make_engine(settings)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
