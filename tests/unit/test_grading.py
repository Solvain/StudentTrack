from decimal import Decimal
from fractions import Fraction

import pytest


@pytest.fixture
def grading():
    from app.services import grading

    return grading


@pytest.mark.parametrize(
    ("mode", "expected"),
    [("subject_means", Fraction(4)), ("all_grades", Fraction(9, 2))],
)
def test_averages(grading, mode, expected):
    result = grading.calculate_statistics({1: [5, 5, 5], 2: [3], 3: []}, mode=mode)

    assert result.subject_averages == {1: Fraction(5), 2: Fraction(3), 3: None}
    assert result.overall_average == expected


@pytest.mark.parametrize("mode", ["subject_means", "all_grades"])
def test_empty_semester(grading, mode):
    result = grading.calculate_statistics({1: []}, mode=mode)

    assert result.subject_averages == {1: None}
    assert result.overall_average is None


@pytest.mark.parametrize(
    ("current", "target", "percent", "reached"),
    [
        (None, Decimal("4.40"), None, None),
        (Fraction(4), None, None, None),
        (Fraction(4), Decimal("4.40"), Fraction(1000, 11), False),
        (Fraction(9, 2), Decimal("4.40"), Fraction(100), True),
        (Fraction(454, 101), Decimal("4.50"), Fraction(90800, 909), False),
    ],
)
def test_progress(grading, current, target, percent, reached):
    result = grading.calculate_progress(current=current, target=target)

    assert result.percent == percent
    assert result.reached is reached


@pytest.mark.parametrize(
    ("mode", "subject_id", "expected"),
    [
        ("subject_means", 2, 5),
        ("all_grades", 2, 4),
        ("subject_means", 3, None),
        ("all_grades", 3, 4),
    ],
)
def test_forecast(grading, mode, subject_id, expected):
    result = grading.minimum_future_grade(
        {1: [5, 5, 5], 2: [3], 3: []},
        {subject_id: 1},
        scale=5,
        target=Decimal("4.40"),
        mode=mode,
    )

    assert result == expected
