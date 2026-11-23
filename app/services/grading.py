from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from math import ceil
from typing import Literal


AveragingMode = Literal["subject_means", "all_grades"]
GradingScale = Literal[5, 12, 100]


@dataclass(frozen=True)
class Statistics:
    subject_averages: dict[int, Fraction | None]
    overall_average: Fraction | None


@dataclass(frozen=True)
class Progress:
    percent: Fraction | None
    reached: bool | None


@dataclass(frozen=True)
class Forecast:
    minimum_uniform_grade: int | None
    best_possible_average: Fraction
    projected_average: Fraction | None


def _overall_average(
    totals: Iterable[tuple[int, int]],
    mode: AveragingMode,
) -> Fraction | None:
    nonempty = [(total, count) for total, count in totals if count]
    if not nonempty:
        return None
    if mode == "all_grades":
        return Fraction(
            sum(total for total, _ in nonempty),
            sum(count for _, count in nonempty),
        )
    return sum(Fraction(total, count) for total, count in nonempty) / len(nonempty)


def calculate_statistics(
    grades_by_subject: Mapping[int, Sequence[int]],
    *,
    mode: AveragingMode,
) -> Statistics:
    totals = {
        subject_id: (sum(grades), len(grades))
        for subject_id, grades in grades_by_subject.items()
    }
    subject_averages = {
        subject_id: Fraction(total, count) if count else None
        for subject_id, (total, count) in totals.items()
    }
    return Statistics(subject_averages, _overall_average(totals.values(), mode))


def calculate_progress(*, current: Fraction | None, target: Decimal | None) -> Progress:
    if current is None or target is None:
        return Progress(percent=None, reached=None)
    exact_target = Fraction(target)
    percent = min(Fraction(100), 100 * current / exact_target)
    return Progress(percent=percent, reached=current >= exact_target)


def calculate_forecast(
    grades_by_subject: Mapping[int, Sequence[int]],
    remaining_by_subject: Mapping[int, int],
    *,
    scale: GradingScale,
    target: Decimal,
    mode: AveragingMode,
) -> Forecast:
    if (
        not remaining_by_subject
        or not remaining_by_subject.keys() <= grades_by_subject.keys()
        or any(count <= 0 for count in remaining_by_subject.values())
    ):
        raise ValueError("The plan must specify positive counts for known subjects.")

    existing_totals = []
    planned_totals = []
    for subject_id, grades in grades_by_subject.items():
        planned_count = remaining_by_subject.get(subject_id, 0)
        final_count = len(grades) + planned_count
        if final_count:
            existing_totals.append((sum(grades), final_count))
            planned_totals.append((planned_count, final_count))

    # The final average equals base + points_per_grade * the uniform grade.
    base = _overall_average(existing_totals, mode)
    points_per_grade = _overall_average(planned_totals, mode)
    assert base is not None and points_per_grade is not None
    best = base + points_per_grade * scale
    exact_target = Fraction(target)
    if best < exact_target:
        return Forecast(None, best, None)

    lowest_grade = 0 if scale == 100 else 1
    required = max(lowest_grade, ceil((exact_target - base) / points_per_grade))
    return Forecast(required, best, base + points_per_grade * required)


def minimum_future_grade(
    grades_by_subject: Mapping[int, Sequence[int]],
    remaining_by_subject: Mapping[int, int],
    *,
    scale: GradingScale,
    target: Decimal,
    mode: AveragingMode,
) -> int | None:
    return calculate_forecast(
        grades_by_subject,
        remaining_by_subject,
        scale=scale,
        target=target,
        mode=mode,
    ).minimum_uniform_grade
