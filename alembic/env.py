"""Alembic environment for AstraNotes.

The SQLAlchemy URL is read (in priority order) from:
  1. The ``ASTRANOTES_DB_URL`` environment variable.
  2. The ``sqlalchemy.url`` setting in ``alembic.ini``.

This lets CI/CD and tests inject a URL without editing the .ini file.
"""
from __future__ import annotations

import os
from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context

# Alembic Config object — access to alembic.ini values.
config = context.config

# Logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import AstraNotes ORM metadata for autogenerate support.
# The import path assumes ``alembic upgrade head`` is run from the project root.
import sys, pathlib  # noqa: E402
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from src.core.notes import _Base  # noqa: E402

target_metadata = _Base.metadata

# Override sqlalchemy.url from environment variable if set.
_env_url = os.environ.get("ASTRANOTES_DB_URL")
if _env_url:
    config.set_main_option("sqlalchemy.url", _env_url)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no live DB connection needed)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
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
        )
        with context.begin_transaction():
            context.run_migrations()
    connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
