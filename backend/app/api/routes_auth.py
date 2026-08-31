from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth.dependencies import CurrentUser, get_current_user
from app.auth.security import create_access_token, hash_password, verify_password
from app.config import get_settings
from app.db.postgres import get_db
from app.models.orm import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(401, "Incorrect username or password")
    token = create_access_token(user.username, user.role)
    return {"access_token": token, "token_type": "bearer", "role": user.role, "username": user.username}


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)):
    return {"username": user.username, "role": user.role}


def seed_default_users(db: Session) -> None:
    """Creates the two demo accounts if no users exist yet. Change these
    credentials via env vars for anything beyond a local demo."""
    if db.query(User).count() > 0:
        return
    settings = get_settings()
    db.add(User(
        username=settings.default_investigator_username,
        hashed_password=hash_password(settings.default_investigator_password),
        role="investigator",
    ))
    db.add(User(
        username=settings.default_admin_username,
        hashed_password=hash_password(settings.default_admin_password),
        role="admin",
    ))
    db.commit()
