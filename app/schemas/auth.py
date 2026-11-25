from typing import Annotated

from pydantic import Field, StringConstraints
from app.schemas.resources import Name, RequestModel, ReadModel

Username = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True,
    min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")]
Password = Annotated[str, Field(min_length=8, max_length=128)]


class RegisterRequest(RequestModel):
    display_name: Name
    username: Username
    password: Password


class LoginRequest(RequestModel):
    username: Username
    password: Annotated[str, Field(min_length=1, max_length=128)]


class AccountRead(ReadModel):
    id: int
    display_name: str
    username: str


class TokenResponse(ReadModel):
    access_token: str
    token_type: str = "bearer"
