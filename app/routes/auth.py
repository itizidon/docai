# app/routes/auth_routes.py
from fastapi import APIRouter, Depends, HTTPException, Response, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models import User
from app.auth import (
    hash_password,
    verify_password,
    set_jwt_cookie,
    remove_jwt_cookie,
    create_token,
    get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# ── SCHEMAS ─────────────────────────────────────────────────────────────────────
class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    role: str

    class Config:
        from_attributes = True


# ── ROUTES ──────────────────────────────────────────────────────────────────────
@router.post("/signup", response_model=UserResponse, status_code=201)
def signup(body: SignupRequest, response: Response, db: Session = Depends(get_db)):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        name=body.name,
        email=body.email,
        hashed_password=hash_password(body.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    set_jwt_cookie(response, user.id)
    return UserResponse.from_orm(user)


@router.post("/login", response_model=UserResponse)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    response: Response = None,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.email == form.username).first()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    set_jwt_cookie(response, user.id)
    return UserResponse.from_orm(user)


@router.post("/logout")
def logout(response: Response):
    remove_jwt_cookie(response)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return current_user