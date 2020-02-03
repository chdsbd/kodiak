from sqlalchemy.orm import Session

from web_api.models import User


def test_basic() -> None:
    assert 2 + 2 == 4


def test_a_transaction(db_session: Session) -> None:
    assert (
        db_session.query(User)
        .filter(User.id == "8F7C2397-50F2-4031-A029-9DA69FC53C10")
        .count()
        == 0
    )

    user = User(
        id="8F7C2397-50F2-4031-A029-9DA69FC53C10",
        github_id=1929960,
        github_login="chdsbd",
        github_access_token="fake-access-token",
    )

    db_session.add(user)
    db_session.commit()


def test_transaction_doesnt_persist(db_session: Session) -> None:
    assert (
        db_session.query(User)
        .filter(User.id == "8F7C2397-50F2-4031-A029-9DA69FC53C10")
        .count()
        == 0
    )
