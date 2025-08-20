"""Authentication routes."""
from datetime import timedelta
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from ..database import SessionDep
from ..models import Token, UserCreate, UserPublic
from ..auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    authenticate_user,
    create_access_token,
    create_user,
    get_current_active_user
)


router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserPublic)
def register_user(user: UserCreate, session: SessionDep):
    """Register a new user."""
    db_user = create_user(
        session=session,
        username=user.username,
        email=user.email,
        password=user.password,
        full_name=user.full_name
    )
    return db_user


@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    session: SessionDep
):
    """Login and get access token."""
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


@router.get("/me", response_model=UserPublic)
def read_users_me(
    current_user: Annotated[UserPublic, Depends(get_current_active_user)],
):
    """Get current user information."""
    return current_user
