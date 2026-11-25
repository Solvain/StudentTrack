from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.api.dependencies import DatabaseSession
from app.models import Student
from app.schemas.auth import AccountRead, LoginRequest, RegisterRequest, TokenResponse
from app.services.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])
# A dummy hash makes unknown usernames incur a password verification as well.
_DUMMY_HASH = hash_password("not-an-account-password")


@router.post("/register", response_model=AccountRead, status_code=201)
def register(payload: RegisterRequest, session: DatabaseSession):
    student = Student(display_name=payload.display_name, username=payload.username,
                      password_hash=hash_password(payload.password))
    session.add(student)
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        if getattr(getattr(error.orig, "diag", None), "constraint_name", None) == "uq_students_username":
            raise HTTPException(409, "Username already exists") from error
        raise
    return student


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, session: DatabaseSession):
    student = session.scalar(select(Student).where(Student.username == payload.username))
    valid = verify_password(payload.password, (student.password_hash if student else None) or _DUMMY_HASH)
    if student is None or not student.password_hash or not valid:
        raise HTTPException(401, "Invalid username or password", headers={"WWW-Authenticate": "Bearer"})
    return TokenResponse(access_token=create_access_token(student.id))
