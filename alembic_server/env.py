"""Alembic environment for the AstraNotes sync server database.

The SQLAlchemy URL is read (in priority order) from:
  1. The ``ASTRANOTES_SERVER_DB_URL`` environment variable.
  2. The ``sqlalchemy.url`` setting in ``alembic_server.ini``.

Run migrations from the project root:
    alembic -c alembic_server.ini upgrade head
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from src.server.models import Base  # noqa: E402

target_metadata = Base.metadata

_env_url = os.environ.get("ASTRANOTES_SERVER_DB_URL")
if _env_url:
    config.set_main_option("sqlalchemy.url", _env_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection needed)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (live DB connection)."""
    url = config.get_main_option("sqlalchemy.url")
    connectable = create_engine(url, poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
