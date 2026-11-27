from collections.abc import Sequence
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.api.dependencies import (
    CurrentStudent,
    DatabaseSession,
    require_grade,
    require_semester,
    require_subject,
)
from app.crud import resources
from app.models import Grade, ScholarshipSettings, Semester, Student, Subject
from app.schemas.resources import (
    MAX_RESOURCE_ID,
    GradeCreate,
    GradeRead,
    GradeUpdate,
    ScholarshipSettingsRead,
    ScholarshipSettingsWrite,
    SemesterCreate,
    SemesterRead,
    SemesterUpdate,
    StudentRead,
    StudentWrite,
    SubjectCreate,
    SubjectRead,
    SubjectUpdate,
)


router = APIRouter(tags=["StudentTrack resources"])
PathId = Annotated[int, Path(gt=0, le=MAX_RESOURCE_ID)]
QueryId = Annotated[int, Query(gt=0, le=MAX_RESOURCE_ID)]

_CONSTRAINT_ERRORS = {
    "fk_semesters_student": (status.HTTP_404_NOT_FOUND, "Student profile not found"),
    "fk_subjects_semester": (status.HTTP_404_NOT_FOUND, "Semester not found"),
    "fk_grades_subject_semester": (status.HTTP_404_NOT_FOUND, "Subject not found"),
    "fk_grades_semester_scale": (
        status.HTTP_409_CONFLICT,
        "Grading scale conflicts with the semester or its grades",
    ),
    "fk_scholarship_settings_semester_scale": (
        status.HTTP_409_CONFLICT,
        "Grading scale conflicts with the scholarship target",
    ),
    "ck_grades_value_range": (status.HTTP_422_UNPROCESSABLE_CONTENT, "Grade is outside the grading scale"),
    "ck_scholarship_settings_target_range": (
        status.HTTP_422_UNPROCESSABLE_CONTENT,
        "Target is outside the grading scale",
    ),
}


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError as error:
        session.rollback()
        constraint = getattr(getattr(error.orig, "diag", None), "constraint_name", None)
        if constraint in _CONSTRAINT_ERRORS:
            code, detail = _CONSTRAINT_ERRORS[constraint]
            raise HTTPException(code, detail) from error
        raise
    except StaleDataError as error:
        session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record no longer exists") from error


def _validate_grade_range(value: int, scale: int) -> None:
    minimum = 0 if scale == 100 else 1
    if not minimum <= value <= scale:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Grade must be between {minimum} and {scale} for this semester",
        )


def _require_scholarship_settings(session: Session, semester_id: int) -> ScholarshipSettings:
    settings = session.get(ScholarshipSettings, semester_id)
    if settings is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scholarship target not set")
    return settings


@router.get("/students/me", response_model=StudentRead)
def get_student(student: CurrentStudent) -> Student:
    return student


@router.patch("/students/me", response_model=StudentRead)
def update_student(payload: StudentWrite, session: DatabaseSession, student: CurrentStudent) -> Student:
    student.display_name = payload.display_name
    _commit(session)
    return student


@router.delete("/students/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(session: DatabaseSession, student: CurrentStudent) -> Response:
    session.delete(student)
    _commit(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/semesters", response_model=list[SemesterRead])
def list_semesters(session: DatabaseSession, student: CurrentStudent) -> Sequence[Semester]:
    return resources.list_semesters(session, student.id)


@router.post("/semesters", response_model=SemesterRead, status_code=status.HTTP_201_CREATED)
def create_semester(payload: SemesterCreate, session: DatabaseSession, student: CurrentStudent) -> Semester:
    semester = Semester(student_id=student.id, **payload.model_dump())
    session.add(semester)
    _commit(session)
    return semester


@router.get("/semesters/{semester_id}", response_model=SemesterRead)
def get_semester(semester_id: PathId, session: DatabaseSession, student: CurrentStudent) -> Semester:
    return require_semester(session, student.id, semester_id)


@router.patch("/semesters/{semester_id}", response_model=SemesterRead)
def update_semester(
    semester_id: PathId, payload: SemesterUpdate, session: DatabaseSession, student: CurrentStudent
) -> Semester:
    semester = require_semester(session, student.id, semester_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(semester, field, value)
    _commit(session)
    return semester


@router.delete("/semesters/{semester_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_semester(semester_id: PathId, session: DatabaseSession, student: CurrentStudent) -> Response:
    semester = require_semester(session, student.id, semester_id)
    session.delete(semester)
    _commit(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/subjects", response_model=list[SubjectRead])
def list_subjects(semester_id: QueryId, session: DatabaseSession, student: CurrentStudent) -> Sequence[Subject]:
    semester = require_semester(session, student.id, semester_id)
    return resources.list_subjects(session, semester.id)


@router.post("/subjects", response_model=SubjectRead, status_code=status.HTTP_201_CREATED)
def create_subject(payload: SubjectCreate, session: DatabaseSession, student: CurrentStudent) -> Subject:
    semester = require_semester(session, student.id, payload.semester_id)
    subject = Subject(semester_id=semester.id, name=payload.name)
    session.add(subject)
    _commit(session)
    return subject


@router.get("/subjects/{subject_id}", response_model=SubjectRead)
def get_subject(subject_id: PathId, session: DatabaseSession, student: CurrentStudent) -> Subject:
    return require_subject(session, student.id, subject_id)


@router.patch("/subjects/{subject_id}", response_model=SubjectRead)
def update_subject(
    subject_id: PathId, payload: SubjectUpdate, session: DatabaseSession, student: CurrentStudent
) -> Subject:
    subject = require_subject(session, student.id, subject_id)
    subject.name = payload.name
    _commit(session)
    return subject


@router.delete("/subjects/{subject_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subject(subject_id: PathId, session: DatabaseSession, student: CurrentStudent) -> Response:
    subject = require_subject(session, student.id, subject_id)
    session.delete(subject)
    _commit(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/grades", response_model=list[GradeRead])
def list_grades(subject_id: QueryId, session: DatabaseSession, student: CurrentStudent) -> Sequence[Grade]:
    subject = require_subject(session, student.id, subject_id)
    return resources.list_grades(session, subject.id)


@router.post("/grades", response_model=GradeRead, status_code=status.HTTP_201_CREATED)
def create_grade(payload: GradeCreate, session: DatabaseSession, student: CurrentStudent) -> Grade:
    subject = require_subject(session, student.id, payload.subject_id)
    semester = require_semester(session, student.id, subject.semester_id, lock=True)
    _validate_grade_range(payload.value, semester.grading_scale)
    grade = Grade(
        subject_id=subject.id,
        semester_id=semester.id,
        grading_scale=semester.grading_scale,
        value=payload.value,
    )
    session.add(grade)
    _commit(session)
    return grade


@router.get("/grades/{grade_id}", response_model=GradeRead)
def get_grade(grade_id: PathId, session: DatabaseSession, student: CurrentStudent) -> Grade:
    return require_grade(session, student.id, grade_id)


@router.patch("/grades/{grade_id}", response_model=GradeRead)
def update_grade(
    grade_id: PathId, payload: GradeUpdate, session: DatabaseSession, student: CurrentStudent
) -> Grade:
    grade = require_grade(session, student.id, grade_id)
    _validate_grade_range(payload.value, grade.grading_scale)
    grade.value = payload.value
    _commit(session)
    return grade


@router.delete("/grades/{grade_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_grade(grade_id: PathId, session: DatabaseSession, student: CurrentStudent) -> Response:
    grade = require_grade(session, student.id, grade_id)
    session.delete(grade)
    _commit(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/semesters/{semester_id}/scholarship-settings", response_model=ScholarshipSettingsRead)
def get_scholarship_settings(
    semester_id: PathId, session: DatabaseSession, student: CurrentStudent
) -> ScholarshipSettings:
    semester = require_semester(session, student.id, semester_id)
    return _require_scholarship_settings(session, semester.id)


@router.put(
    "/semesters/{semester_id}/scholarship-settings",
    response_model=ScholarshipSettingsRead,
    responses={status.HTTP_201_CREATED: {"model": ScholarshipSettingsRead}},
)
def put_scholarship_settings(
    semester_id: PathId,
    payload: ScholarshipSettingsWrite,
    response: Response,
    session: DatabaseSession,
    student: CurrentStudent,
) -> ScholarshipSettings:
    semester = require_semester(session, student.id, semester_id, lock=True)
    minimum = Decimal("0.01") if semester.grading_scale == 100 else Decimal(1)
    if not minimum <= payload.target_average <= semester.grading_scale:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Target must be between {minimum} and {semester.grading_scale} for this semester",
        )
    target = payload.target_average.quantize(Decimal("0.01"))
    settings, created = resources.save_scholarship_settings(session, semester, target)
    _commit(session)
    if created:
        response.status_code = status.HTTP_201_CREATED
    return settings


@router.delete("/semesters/{semester_id}/scholarship-settings", status_code=status.HTTP_204_NO_CONTENT)
def delete_scholarship_settings(semester_id: PathId, session: DatabaseSession, student: CurrentStudent) -> Response:
    semester = require_semester(session, student.id, semester_id, lock=True)
    settings = _require_scholarship_settings(session, semester.id)
    session.delete(settings)
    _commit(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
