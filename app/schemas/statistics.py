from typing import Annotated

from pydantic import BaseModel, Field

from app.schemas.resources import MAX_RESOURCE_ID, RequestModel, ResourceId
from app.services.grading import AveragingMode, GradingScale


class SubjectStatistics(BaseModel):
    id: int
    name: str
    average: float | None
    grade_count: int


class StatisticsResponse(BaseModel):
    semester_id: int
    grading_scale: GradingScale
    averaging_mode: AveragingMode
    overall_average: float | None
    subjects: list[SubjectStatistics]
    grade_count: int


class ProgressResponse(BaseModel):
    semester_id: int
    current_average: float | None
    target_average: float | None
    progress_percent: float | None
    goal_reached: bool | None


PositiveCount = Annotated[int, Field(gt=0, strict=True)]
SubjectId = Annotated[int, Field(gt=0, le=MAX_RESOURCE_ID)]


class ForecastRequest(RequestModel):
    semester_id: ResourceId
    remaining_by_subject: Annotated[dict[SubjectId, PositiveCount], Field(min_length=1)]


class ForecastResponse(BaseModel):
    semester_id: int
    target_average: float
    minimum_uniform_grade: int | None
    best_possible_average: float
    possible: bool
    projected_average: float | None
