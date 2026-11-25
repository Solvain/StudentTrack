import pytest


def create_semester(client, mode="subject_means", scale=5):
    response = client.post(
        "/api/semesters",
        json={"name": "Semester", "grading_scale": scale, "averaging_mode": mode},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def create_subject(client, semester_id, name):
    response = client.post("/api/subjects", json={"semester_id": semester_id, "name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def add_grades(client, subject_id, values):
    for value in values:
        response = client.post("/api/grades", json={"subject_id": subject_id, "value": value})
        assert response.status_code == 201, response.text


def set_target(client, semester_id, target):
    response = client.put(
        f"/api/semesters/{semester_id}/scholarship-settings",
        json={"target_average": target},
    )
    assert response.status_code == 201, response.text


@pytest.fixture
def profile_client(client):
    from auth_helpers import register_and_login
    register_and_login(client), response.text
    return client


@pytest.fixture
def performance(profile_client):
    def create(mode):
        semester_id = create_semester(profile_client, mode)
        first_subject = create_subject(profile_client, semester_id, "Math")
        second_subject = create_subject(profile_client, semester_id, "Physics")
        empty_subject = create_subject(profile_client, semester_id, "History")
        add_grades(profile_client, first_subject, [5, 5, 5])
        add_grades(profile_client, second_subject, [3])
        set_target(profile_client, semester_id, "4.40")
        return semester_id, first_subject, second_subject, empty_subject

    return create


@pytest.mark.parametrize(
    "mode,average,percent,reached",
    [("subject_means", 4, 90.91, False), ("all_grades", 4.5, 100, True)],
)
def test_statistics_and_progress(profile_client, performance, mode, average, percent, reached):
    semester_id, first, second, empty = performance(mode)
    params = {"semester_id": semester_id}
    stats = profile_client.get("/api/statistics", params=params)
    progress = profile_client.get("/api/scholarship/progress", params=params)

    assert stats.status_code == 200, stats.text
    body = stats.json()
    assert body["semester_id"] == semester_id
    assert body["grading_scale"] == 5
    assert body["averaging_mode"] == mode
    assert body["overall_average"] == average
    assert body["grade_count"] == 4
    assert {subject["id"]: subject for subject in body["subjects"]} == {
        first: {"id": first, "name": "Math", "average": 5, "grade_count": 3},
        second: {"id": second, "name": "Physics", "average": 3, "grade_count": 1},
        empty: {"id": empty, "name": "History", "average": None, "grade_count": 0},
    }
    assert progress.status_code == 200, progress.text
    assert progress.json() == {
        "semester_id": semester_id,
        "current_average": average,
        "target_average": 4.4,
        "progress_percent": percent,
        "goal_reached": reached,
    }


@pytest.mark.parametrize(
    "mode,plan_on_empty,required,best,projected",
    [
        ("subject_means", False, 5, 4.5, 4.5),
        ("all_grades", False, 4, 4.6, 4.4),
        ("subject_means", True, None, 4.33, None),
        ("all_grades", True, 4, 4.6, 4.4),
    ],
)
def test_forecast(profile_client, performance, mode, plan_on_empty, required, best, projected):
    semester_id, _, second, empty = performance(mode)
    subject_id = empty if plan_on_empty else second
    response = profile_client.post(
        "/api/scholarship/forecast",
        json={"semester_id": semester_id, "remaining_by_subject": {str(subject_id): 1}},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "semester_id": semester_id,
        "target_average": 4.4,
        "minimum_uniform_grade": required,
        "best_possible_average": best,
        "possible": required is not None,
        "projected_average": projected,
    }


def test_empty_progress_and_forecast_without_goal(profile_client):
    semester_id = create_semester(profile_client)
    subject_id = create_subject(profile_client, semester_id, "Math")
    params = {"semester_id": semester_id}

    progress = profile_client.get("/api/scholarship/progress", params=params)
    assert progress.status_code == 200, progress.text
    assert progress.json() == {
        "semester_id": semester_id,
        "current_average": None,
        "target_average": None,
        "progress_percent": None,
        "goal_reached": None,
    }
    request = {"semester_id": semester_id, "remaining_by_subject": {str(subject_id): 2}}
    assert profile_client.post("/api/scholarship/forecast", json=request).status_code == 409

    set_target(profile_client, semester_id, "4.00")

    progress = profile_client.get("/api/scholarship/progress", params=params)
    assert progress.status_code == 200, progress.text
    assert progress.json()["target_average"] == 4
    assert progress.json()["progress_percent"] is None
    assert progress.json()["goal_reached"] is None
    forecast = profile_client.post("/api/scholarship/forecast", json=request)
    assert forecast.status_code == 200, forecast.text
    assert forecast.json()["minimum_uniform_grade"] == 4


def test_zero_is_a_grade_and_can_be_enough_for_forecast(profile_client):
    semester_id = create_semester(profile_client, scale=100)
    subject_id = create_subject(profile_client, semester_id, "Math")
    add_grades(profile_client, subject_id, [0, 100])
    set_target(profile_client, semester_id, "30.00")

    stats = profile_client.get("/api/statistics", params={"semester_id": semester_id})
    assert stats.status_code == 200, stats.text
    assert stats.json()["overall_average"] == 50
    assert stats.json()["grade_count"] == 2

    forecast = profile_client.post(
        "/api/scholarship/forecast",
        json={"semester_id": semester_id, "remaining_by_subject": {str(subject_id): 1}},
    )
    assert forecast.status_code == 200, forecast.text
    assert forecast.json()["minimum_uniform_grade"] == 0
    assert forecast.json()["possible"] is True
    assert forecast.json()["projected_average"] == 33.33


def test_statistics_without_subjects_and_with_unknown_semester(profile_client):
    semester_id = create_semester(profile_client)
    stats = profile_client.get("/api/statistics", params={"semester_id": semester_id})
    assert stats.status_code == 200, stats.text
    assert stats.json() == {
        "semester_id": semester_id,
        "grading_scale": 5,
        "averaging_mode": "subject_means",
        "overall_average": None,
        "subjects": [],
        "grade_count": 0,
    }
    missing = profile_client.get("/api/statistics", params={"semester_id": semester_id + 1})
    assert missing.status_code == 404, missing.text


@pytest.mark.parametrize("counts", [{}, {"1": 0}, {"1": -1}, {"1": True}, {"1": "2"}, {"0": 1}])
def test_forecast_rejects_invalid_plan(profile_client, counts):
    semester_id = create_semester(profile_client)
    response = profile_client.post(
        "/api/scholarship/forecast",
        json={"semester_id": semester_id, "remaining_by_subject": counts},
    )

    assert response.status_code == 422, response.text


def test_forecast_rejects_subject_from_another_semester(profile_client, performance):
    semester_id, *_ = performance("subject_means")
    other_semester = create_semester(profile_client)
    other_subject = create_subject(profile_client, other_semester, "Other")

    response = profile_client.post(
        "/api/scholarship/forecast",
        json={"semester_id": semester_id, "remaining_by_subject": {str(other_subject): 1}},
    )

    assert response.status_code == 404, response.text


@pytest.mark.parametrize("route", ["/api/statistics", "/api/scholarship/progress"])
def test_read_endpoints_reject_ids_outside_postgresql_integer_range(profile_client, route):
    response = profile_client.get(route, params={"semester_id": 2**31})

    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    "semester_id,remaining_by_subject",
    [(2**31, {"1": 1}), (1, {str(2**31): 1})],
)
def test_forecast_rejects_ids_outside_postgresql_integer_range(
    profile_client,
    semester_id,
    remaining_by_subject,
):
    response = profile_client.post(
        "/api/scholarship/forecast",
        json={"semester_id": semester_id, "remaining_by_subject": remaining_by_subject},
    )

    assert response.status_code == 422, response.text
