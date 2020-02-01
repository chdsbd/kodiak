from sqlalchemy import Column, ForeignKey, Integer, String, Boolean, DateTime, func
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB

Base = declarative_base()


class Model(Base):
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )


class Session(Model):
    """
    Session object with user session information.

    Data is stored on the server side and a session ID in a cookie maps to this
    on the client side.
    """

    session_key = Column(String, unique=True, index=True, nullable=False)
    session_data = Column(JSONB, nullable=False)

    user_id = Column(UUID(as_uuid=True), ForeignKey("user.id"), nullable=False)
    user = relationship("User", back_populates="sessions")


class User(Model):
    """
    A user of the web application.

    This actor can login and view the dashboard. They map one-to-one to a GitHub account.
    """

    __tablename__ = "user"
    github_id = Column(Integer, unique=True, index=True, nullable=False)
    github_username = Column(String, unique=True, index=True, nullable=False)
    github_access_token = Column(String, nullable=False)

    sessions = relationship("Session", back_populates="user")
