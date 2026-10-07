import os
from logging.config import fileConfig
from dotenv import load_dotenv

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from sqlalchemy.engine import make_url

from alembic import context

# Load environment variables from .env
load_dotenv()

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Migrations are privileged operations and must use their dedicated credential.
# Never fall back to DATABASE_URL, which may be an application runtime role.
database_url = os.getenv("DATABASE_URL_MIGRATIONS")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL_MIGRATIONS is required for Alembic; generic DATABASE_URL is not accepted."
    )
# Pin the synchronous PostgreSQL driver used by this migration environment;
# SQLAlchemy's bare postgresql:// dialect may otherwise select psycopg v3.
migration_url = make_url(database_url).set(drivername="postgresql+psycopg2")
config.set_main_option(
    "sqlalchemy.url",
    migration_url.render_as_string(hide_password=False).replace("%", "%%"),
)

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
