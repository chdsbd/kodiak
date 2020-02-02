import os

from dotenv import load_dotenv
from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate

from web_api.models import db

load_dotenv()


migrate = Migrate()
login_manager = LoginManager()


def create_app(config: dict = None) -> Flask:
    app = Flask(__name__)
    app.config["GITHUB_CLIENT_ID"] = os.environ.get("GITHUB_CLIENT_ID")
    app.config["GITHUB_CLIENT_SECRET"] = os.environ.get("GITHUB_CLIENT_SECRET")
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    app.config["KODIAK_API_AUTH_REDIRECT_URL"] = os.environ.get(
        "KODIAK_API_AUTH_REDIRECT_URL"
    )
    app.config["KODIAK_WEB_AUTHED_LANDING_PATH"] = os.environ.get(
        "KODIAK_WEB_AUTHED_LANDING_PATH"
    )

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    return app
