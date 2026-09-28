"""`/auth/login`, `/auth/logout`, `/auth/me` — contrat §2.2."""

from __future__ import annotations

from pydantic import BaseModel, Field


class LoginBody(BaseModel):
    # Borne haute : scrypt accepte tout, mais inutile de hacher un corps de plusieurs Mo.
    password: str = Field(min_length=1, max_length=1024)


class AuthStatus(BaseModel):
    authenticated: bool
    auth_enabled: bool
