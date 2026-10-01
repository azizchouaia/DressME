from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User


def ensure_demo_user(db: Session) -> None:
    from app.api.routes.auth import create_user

    settings = get_settings()
    if db.scalar(select(User).where(User.email == settings.demo_email)):
        return
    create_user(db, settings.demo_email, settings.demo_password, settings.demo_name)
    db.commit()


if __name__ == "__main__":
    from app.db.session import SessionLocal

    with SessionLocal() as session:
        ensure_demo_user(session)
    print("Demo user ready.")
