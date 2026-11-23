from decimal import Decimal
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.services.grading import AveragingMode, GradingScale


Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
MAX_RESOURCE_ID = 2**31 - 1
ResourceId = Annotated[int, Field(strict=True, gt=0, le=MAX_RESOURCE_ID)]
GradeValue = Annotated[int, Field(strict=True, ge=0, le=100)]
TargetAverage = Annotated[Decimal, Field(gt=0, le=100, max_digits=5, decimal_places=2)]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class StudentWrite(RequestModel):
    display_name: Name


class StudentRead(ReadModel):
    id: int
    display_name: str


class SemesterCreate(RequestModel):
    name: Name
    grading_scale: GradingScale
    averaging_mode: AveragingMode = "subject_means"


class SemesterUpdate(RequestModel):
    name: Name | None = None
    grading_scale: GradingScale | None = None
    averaging_mode: AveragingMode | None = None

    @model_validator(mode="after")
    def reject_null_fields(self) -> Self:
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class SemesterRead(ReadModel):
    id: int
    student_id: int
    name: str
    grading_scale: GradingScale
    averaging_mode: AveragingMode


class SubjectUpdate(RequestModel):
    name: Name


class SubjectCreate(SubjectUpdate):
    semester_id: ResourceId


class SubjectRead(ReadModel):
    id: int
    semester_id: int
    name: str


class GradeUpdate(RequestModel):
    value: GradeValue


class GradeCreate(GradeUpdate):
    subject_id: ResourceId


class GradeRead(ReadModel):
    id: int
    subject_id: int
    semester_id: int
    grading_scale: GradingScale
    value: int


class ScholarshipSettingsWrite(RequestModel):
    target_average: TargetAverage


class ScholarshipSettingsRead(ReadModel):
    semester_id: int
    grading_scale: GradingScale
    target_average: Decimal
