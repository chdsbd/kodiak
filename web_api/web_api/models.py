from uuid import uuid4

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID

db = SQLAlchemy()


class Base(db.Model):  # type: ignore
    __abstract__ = True

    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=db.text("gen_random_uuid()"),
        index=True,
        nullable=False,
    )
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=db.func.now(),
        server_default=db.func.now(),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=db.func.now(),
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )


class User(UserMixin, Base):
    """
    A user of the web application.

    This actor can login and view the dashboard. They map one-to-one to a GitHub account.
    """

    __tablename__ = "user"
    github_id = db.Column(db.Integer, unique=True, index=True, nullable=False)
    github_login = db.Column(db.String, unique=True, index=True, nullable=False)
    github_access_token = db.Column(db.String, nullable=False)
