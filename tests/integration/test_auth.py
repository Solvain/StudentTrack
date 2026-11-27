from fastapi.testclient import TestClient

from auth_helpers import register_and_login


def test_rejects_missing_token_bad_password_and_invalid_token(client):
    response = client.get("/api/semesters")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"

    register_and_login(client, "alice")
    response = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert response.status_code == 401
    assert client.get("/api/students/me", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_accounts_are_isolated(client):
    register_and_login(client, "alice", name="Alice")
    semester = client.post("/api/semesters", json={"name": "Private", "grading_scale": 12})
    assert semester.status_code == 201, semester.text
    semester_id = semester.json()["id"]
    semester_path = f"/api/semesters/{semester_id}"

    subject = client.post("/api/subjects", json={"semester_id": semester_id, "name": "Math"})
    assert subject.status_code == 201, subject.text
    subject_id = subject.json()["id"]
    subject_path = f"/api/subjects/{subject_id}"

    grade = client.post("/api/grades", json={"subject_id": subject_id, "value": 11})
    assert grade.status_code == 201, grade.text
    grade_path = f"/api/grades/{grade.json()['id']}"
    settings_path = f"{semester_path}/scholarship-settings"
    settings = client.put(settings_path, json={"target_average": "11.50"})
    assert settings.status_code == 201, settings.text

    statistics_path = f"/api/statistics?semester_id={semester_id}"
    progress_path = f"/api/scholarship/progress?semester_id={semester_id}"
    forecast = {"semester_id": semester_id, "remaining_by_subject": {str(subject_id): 1}}

    with TestClient(client.app) as other:
        register_and_login(other, "bob", name="Bob")
        assert other.get("/api/students/me").json()["display_name"] == "Bob"
        assert other.get("/api/semesters").json() == []

        for path, update in (
            (semester_path, {"name": "Changed"}),
            (subject_path, {"name": "Changed"}),
            (grade_path, {"value": 10}),
        ):
            assert other.get(path).status_code == 404, path
            assert other.patch(path, json=update).status_code == 404, path
            assert other.delete(path).status_code == 404, path

        assert other.get(f"/api/subjects?semester_id={semester_id}").status_code == 404
        assert other.get(f"/api/grades?subject_id={subject_id}").status_code == 404
        assert other.post("/api/subjects", json={"semester_id": semester_id, "name": "Other"}).status_code == 404
        assert other.post("/api/grades", json={"subject_id": subject_id, "value": 10}).status_code == 404
        assert other.get(settings_path).status_code == 404
        assert other.put(settings_path, json={"target_average": "10.00"}).status_code == 404
        assert other.delete(settings_path).status_code == 404
        assert other.get(statistics_path).status_code == 404
        assert other.get(progress_path).status_code == 404
        assert other.post("/api/scholarship/forecast", json=forecast).status_code == 404

        other_semester = other.post("/api/semesters", json={"name": "Bob's semester", "grading_scale": 12})
        assert other_semester.status_code == 201, other_semester.text
        other_semester_id = other_semester.json()["id"]
        assert client.get(f"/api/semesters/{other_semester_id}").status_code == 404
        assert other.delete("/api/students/me").status_code == 204
        assert other.get("/api/students/me").status_code == 401

    assert client.get("/api/students/me").json()["display_name"] == "Alice"
    assert client.get("/api/semesters").json() == [semester.json()]
    assert client.get(subject_path).json() == subject.json()
    assert client.get(grade_path).json() == grade.json()
    assert client.get(settings_path).json() == settings.json()
    assert client.get(statistics_path).json()["overall_average"] == 11
    assert client.get(progress_path).json()["target_average"] == 11.5
    assert client.post("/api/scholarship/forecast", json=forecast).status_code == 200


def test_auth_validation_returns_only_public_error_fields(client):
    for action in ("register", "login"):
        response = client.post(f"/api/auth/{action}", json={"display_name": "Student"})
        assert response.status_code == 422
        errors = response.json()["detail"]
        assert errors
        assert all(set(error) == {"loc", "msg", "type"} for error in errors)
