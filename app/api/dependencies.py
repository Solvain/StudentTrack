from typing import Annotated

from jwt.exceptions import InvalidTokenError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.security import decode_student_id

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.crud import resources
from app.db import get_session
from app.models import Grade, Semester, Student, Subject


DatabaseSession = Annotated[Session, Depends(get_session)]


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_student(
    session: DatabaseSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> Student:
    error = HTTPException(401, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise error
    try:
        student_id = decode_student_id(credentials.credentials)
    except (InvalidTokenError, ValueError, TypeError) as exc:
        raise error from exc
    student = session.get(Student, student_id)
    if student is None or student.password_hash is None:
        raise error
    return student


CurrentStudent = Annotated[Student, Depends(get_current_student)]


def require_semester(
    session: Session, student_id: int, semester_id: int, *, lock: bool = False
) -> Semester:
    semester = resources.get_semester(session, student_id, semester_id, lock=lock)
    if semester is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Semester not found")
    return semester


def require_subject(session: Session, student_id: int, subject_id: int) -> Subject:
    subject = resources.get_subject(session, student_id, subject_id)
    if subject is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Subject not found")
    return subject


def require_grade(session: Session, student_id: int, grade_id: int) -> Grade:
    grade = resources.get_grade(session, student_id, grade_id)
    if grade is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grade not found")
    return grade
