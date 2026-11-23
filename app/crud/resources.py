from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Grade, ScholarshipSettings, Semester, Student, Subject


def get_local_student(session: Session) -> Student | None:
    return session.scalar(select(Student).where(Student.local_slot == 1))


def list_semesters(session: Session, student_id: int) -> Sequence[Semester]:
    query = select(Semester).where(Semester.student_id == student_id).order_by(Semester.id)
    return session.scalars(query).all()


def get_semester(
    session: Session, student_id: int, semester_id: int, *, lock: bool = False
) -> Semester | None:
    query = select(Semester).where(Semester.id == semester_id, Semester.student_id == student_id)
    if lock:
        query = query.with_for_update()
    return session.scalar(query)


def list_subjects(session: Session, semester_id: int) -> Sequence[Subject]:
    query = select(Subject).where(Subject.semester_id == semester_id).order_by(Subject.id)
    return session.scalars(query).all()


def get_subject(session: Session, student_id: int, subject_id: int) -> Subject | None:
    query = (
        select(Subject)
        .join(Subject.semester)
        .where(Subject.id == subject_id, Semester.student_id == student_id)
    )
    return session.scalar(query)


def list_grades(session: Session, subject_id: int) -> Sequence[Grade]:
    query = select(Grade).where(Grade.subject_id == subject_id).order_by(Grade.id)
    return session.scalars(query).all()


def get_grade(session: Session, student_id: int, grade_id: int) -> Grade | None:
    query = (
        select(Grade)
        .join(Semester, Grade.semester_id == Semester.id)
        .where(Grade.id == grade_id, Semester.student_id == student_id)
    )
    return session.scalar(query)


def save_scholarship_settings(
    session: Session, semester: Semester, target: Decimal
) -> tuple[ScholarshipSettings, bool]:
    settings = session.get(ScholarshipSettings, semester.id)
    if settings is not None:
        settings.target_average = target
        return settings, False

    settings = ScholarshipSettings(
        semester_id=semester.id,
        grading_scale=semester.grading_scale,
        target_average=target,
    )
    session.add(settings)
    return settings, True
