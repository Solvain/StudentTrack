from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.crud import resources
from app.db import get_session
from app.models import Grade, Semester, Student, Subject


DatabaseSession = Annotated[Session, Depends(get_session)]


def get_current_student(session: DatabaseSession) -> Student:
    student = resources.get_local_student(session)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student profile not found")
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
