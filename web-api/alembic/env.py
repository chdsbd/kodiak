import databases
from alembic import context
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, pool
from starlette.config import Config as AppConfig

from app.db.models import Base

app_config = AppConfig(".env")
DATABASE_URL = app_config("DATABASE_URL", cast=databases.DatabaseURL)

alembic_config = AlembicConfig()
alembic_config.set_main_option("script_location", "app:migrations")
alembic_config.set_main_option("timezone", "UTC")

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    context.configure(
        url=str(DATABASE_URL),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # compare_type was specified in the fastapi cookie cutter project and is
        # not a default on generation:
        # https://alembic.sqlalchemy.org/en/latest/autogenerate.html?highlight=compare_type#comparing-types
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = create_engine(str(DATABASE_URL), poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # compare_type was specified in the fastapi cookie cutter project
            # and is not a default on generation:
            # https://alembic.sqlalchemy.org/en/latest/autogenerate.html?highlight=compare_type#comparing-types
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
