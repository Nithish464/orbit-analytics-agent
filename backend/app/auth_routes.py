
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from .auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_current_user,
    require_role,
)


router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)


class RegisterRequest(BaseModel):
    email: str = Field(
        min_length=5,
        max_length=254,
    )
    password: str = Field(
        min_length=12,
        max_length=72,
    )


class LoginRequest(BaseModel):
    email: str = Field(
        min_length=5,
        max_length=254,
    )
    password: str = Field(
        min_length=1,
        max_length=72,
    )


def _public_user(user: dict) -> dict:
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "role": user["role"],
        "is_active": bool(user["is_active"]),
        "created_at": user["created_at"],
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest):
    try:
        user = create_user(
            email=request.email,
            password=request.password,
        )

        token = create_access_token(user["user_id"])

        return {
            "message": "Registration successful.",
            "access_token": token,
            "token_type": "bearer",
            "user": _public_user(user),
        }

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@router.post("/login")
def login(request: LoginRequest):
    user = authenticate_user(
        email=request.email,
        password=request.password,
    )

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(user["user_id"])

    return {
        "message": "Login successful.",
        "access_token": token,
        "token_type": "bearer",
        "user": _public_user(user),
    }


@router.get("/me")
def get_profile(
    current_user: dict = Depends(get_current_user),
):
    return {
        "user": _public_user(current_user),
    }


@router.get("/admin")
def admin_dashboard(
    current_user: dict = Depends(require_role("admin")),
):
    return {
        "message": "Admin access granted.",
        "user": _public_user(current_user),
    }
