from __future__ import annotations

# pyright: reportMissingImports=false

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from services.api.app.config import get_settings
from services.api.app.db import Base
# Import model modules for side effects: registers all tables on `Base.metadata`
# for autogenerate and `compare_type` diffs.
from services.api.app import models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _set_url_from_settings() -> None:
    settings = get_settings()
    config.set_main_option("sqlalchemy.url", settings.get_migration_database_url())


def run_migrations_offline() -> None:
    _set_url_from_settings()
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    _set_url_from_settings()
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
