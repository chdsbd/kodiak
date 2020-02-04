"""
The database, app, and _db fixtures are based on the examples provided by
https://github.com/jeancochrane/pytest-flask-sqlalchemy/blob/b6b9f846977e7981a0ec69d969eceb99ddee58f7/README.md#conftest-setup

pytest-flask-sqlalchemy is critical in replicating the built in testing features
of Django.
"""

import os
from pathlib import Path
from typing import Any

import pytest
import sqlalchemy
from alembic import command
from flask import Flask, current_app
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL as DatabaseURL

from web_api.config import create_app

# specify the absolute path to ensure we can run pytest from any directory.
migrations_path = str(Path(__file__).parent.parent / "migrations")


@pytest.fixture(scope="session")
def database_url(request: Any) -> DatabaseURL:
    """
    Create an explicit test database url base on the provided one. This ensures
    we don't accidentally destroy an active database when testing and matches
    the behavior of Django.
    """
    url = sqlalchemy.engine.url.make_url(os.environ.get("DATABASE_URL", "postgresql://postgres@127.0.0.1:5432/postgres"))
    url.database = f"test_{url.database}"
    return url


@pytest.fixture(scope="session")
def database(request: Any, app: Flask, database_url: DatabaseURL) -> None:
    """
    Create a Postgres database for the tests, and drop it when the tests are done.
    """

    # connect to the 'postgres' database so we can create our new database if it
    # doesn't exist. We'd get an error if we tried to connect to a non-existent
    # database.
    root_db_url = sqlalchemy.engine.url.make_url(str(database_url))
    root_db_url.database = "postgres"
    # AUTOCOMMIT is needed to run CREATE DATABASE, which will not work in a transaction.
    engine = create_engine(root_db_url, isolation_level="AUTOCOMMIT")
    database_exists = (
        engine.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s;", [database_url.database]
        ).fetchone()
        is not None
    )
    if not database_exists:
        engine.execute("CREATE DATABASE {database_url.database}")
    # run our alembic migrations on our database.
    with app.app_context():  # type: ignore
        # I tried calling `flask_migrate.upgrade`, but that triggers a SysExit
        # exception, probably because it's for a CLI.
        #
        # related: https://github.com/miguelgrinberg/Flask-Migrate/issues/69#issuecomment-138394391
        config = current_app.extensions["migrate"].migrate.get_config(migrations_path)
        command.upgrade(config, "head")

    @request.addfinalizer
    def drop_database() -> None:
        # TODO(chdsbd): make database dropping configurable. It's faster to keep the
        # database around, but when migrations get messy locally, it's nice to
        # be able to easily wipe the database.
        #
        # We would call DROP DATABASE here.
        pass


@pytest.fixture(scope="session")
def app(database_url: DatabaseURL) -> Flask:
    """
    Create a Flask app context for the tests.
    """

    app = create_app(
        SQLALCHEMY_DATABASE_URI=str(database_url),
        SECRET_KEY=str(os.urandom(24)),
        GITHUB_CLIENT_ID="00000",
        GITHUB_CLIENT_SECRET="github-client-secret",
    )
    app.testing = True

    return app


@pytest.fixture(scope="session")
def _db(app: Flask, database: object) -> SQLAlchemy:
    """
    Provide the transactional fixtures with access to the database via a
    Flask-SQLAlchemy database connection.
    """
    return SQLAlchemy(app=app)
