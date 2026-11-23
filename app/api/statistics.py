from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import CurrentStudent, DatabaseSession
from app.models import Grade, ScholarshipSettings, Semester, Subject
from app.schemas.resources import MAX_RESOURCE_ID
from app.schemas.statistics import (
    ForecastRequest,
    ForecastResponse,
    ProgressResponse,
    StatisticsResponse,
    SubjectStatistics,
)
from app.services import grading


router = APIRouter(tags=["statistics"])

SemesterQuery = Annotated[int, Query(gt=0, le=MAX_RESOURCE_ID)]


@dataclass
class SemesterData:
    grading_scale: grading.GradingScale
    averaging_mode: grading.AveragingMode
    target_average: Decimal | None
    subject_names: dict[int, str]
    grades_by_subject: dict[int, list[int]]


def _load_semester(session: Session, student_id: int, semester_id: int) -> SemesterData:
    # Fetch the mode, goal, subjects, and grades from one database snapshot.
    rows = session.execute(
        select(
            Semester.grading_scale,
            Semester.averaging_mode,
            ScholarshipSettings.target_average,
            Subject.id.label("subject_id"),
            Subject.name.label("subject_name"),
            Grade.value.label("grade_value"),
        )
        .select_from(Semester)
        .outerjoin(ScholarshipSettings, ScholarshipSettings.semester_id == Semester.id)
        .outerjoin(Subject, Subject.semester_id == Semester.id)
        .outerjoin(Grade, Grade.subject_id == Subject.id)
        .where(Semester.id == semester_id, Semester.student_id == student_id)
        .order_by(Subject.id)
    ).all()
    if not rows:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Semester not found")

    first_row = rows[0]
    subject_names: dict[int, str] = {}
    grades_by_subject: dict[int, list[int]] = {}
    for row in rows:
        if row.subject_id is None:
            continue
        subject_names[row.subject_id] = row.subject_name
        grades = grades_by_subject.setdefault(row.subject_id, [])
        if row.grade_value is not None:
            grades.append(row.grade_value)

    return SemesterData(
        grading_scale=first_row.grading_scale,
        averaging_mode=first_row.averaging_mode,
        target_average=first_row.target_average,
        subject_names=subject_names,
        grades_by_subject=grades_by_subject,
    )


def _rounded(value: Fraction | Decimal) -> float:
    return float(round(value, 2))


def _optional_rounded(value: Fraction | Decimal | None) -> float | None:
    return None if value is None else _rounded(value)


@router.get("/statistics")
def read_statistics(
    semester_id: SemesterQuery,
    session: DatabaseSession,
    student: CurrentStudent,
) -> StatisticsResponse:
    semester = _load_semester(session, student.id, semester_id)
    result = grading.calculate_statistics(
        semester.grades_by_subject,
        mode=semester.averaging_mode,
    )
    subjects = [
        SubjectStatistics(
            id=subject_id,
            name=semester.subject_names[subject_id],
            average=_optional_rounded(result.subject_averages[subject_id]),
            grade_count=len(grades),
        )
        for subject_id, grades in semester.grades_by_subject.items()
    ]
    return StatisticsResponse(
        semester_id=semester_id,
        grading_scale=semester.grading_scale,
        averaging_mode=semester.averaging_mode,
        overall_average=_optional_rounded(result.overall_average),
        subjects=subjects,
        grade_count=sum(subject.grade_count for subject in subjects),
    )


@router.get("/scholarship/progress")
def read_progress(
    semester_id: SemesterQuery,
    session: DatabaseSession,
    student: CurrentStudent,
) -> ProgressResponse:
    semester = _load_semester(session, student.id, semester_id)
    statistics = grading.calculate_statistics(
        semester.grades_by_subject,
        mode=semester.averaging_mode,
    )
    progress = grading.calculate_progress(
        current=statistics.overall_average,
        target=semester.target_average,
    )
    return ProgressResponse(
        semester_id=semester_id,
        current_average=_optional_rounded(statistics.overall_average),
        target_average=_optional_rounded(semester.target_average),
        progress_percent=_optional_rounded(progress.percent),
        goal_reached=progress.reached,
    )


@router.post("/scholarship/forecast")
def read_forecast(
    request: ForecastRequest,
    session: DatabaseSession,
    student: CurrentStudent,
) -> ForecastResponse:
    semester = _load_semester(session, student.id, request.semester_id)
    if not request.remaining_by_subject.keys() <= semester.grades_by_subject.keys():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A subject in the plan was not found in this semester.",
        )
    if semester.target_average is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Set a scholarship target before forecasting.",
        )
    result = grading.calculate_forecast(
        semester.grades_by_subject,
        request.remaining_by_subject,
        scale=semester.grading_scale,
        target=semester.target_average,
        mode=semester.averaging_mode,
    )
    return ForecastResponse(
        semester_id=request.semester_id,
        target_average=_rounded(semester.target_average),
        minimum_uniform_grade=result.minimum_uniform_grade,
        best_possible_average=_rounded(result.best_possible_average),
        possible=result.minimum_uniform_grade is not None,
        projected_average=_optional_rounded(result.projected_average),
    )
