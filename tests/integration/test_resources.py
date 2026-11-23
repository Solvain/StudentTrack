import pytest
from sqlalchemy import text


def create_semester(client, *, scale=5):
    response = client.post("/api/students", json={"display_name": "Мария"})
    assert response.status_code == 201
    response = client.post("/api/semesters", json={"name": "Осень", "grading_scale": scale})
    assert response.status_code == 201
    return response.json()["id"]


def create_subject(client, semester_id, name="Математика"):
    response = client.post("/api/subjects", json={"semester_id": semester_id, "name": name})
    assert response.status_code == 201
    return response.json()["id"]


def test_local_profile_and_owned_semester_lifecycle(client):
    assert client.get("/api/students/me").status_code == 404

    semester_id = create_semester(client, scale=12)
    profile = client.get("/api/students/me")
    assert profile.status_code == 200
    assert profile.json()["display_name"] == "Мария"
    assert client.post("/api/students", json={"display_name": "Другой"}).status_code == 409

    profile = client.patch("/api/students/me", json={"display_name": "  Мария С.  "})
    assert profile.status_code == 200
    assert profile.json()["display_name"] == "Мария С."
    assert client.get("/api/semesters").json()[0]["id"] == semester_id

    semester = client.patch(
        f"/api/semesters/{semester_id}",
        json={"name": "Весна", "grading_scale": 100, "averaging_mode": "all_grades"},
    )
    assert semester.status_code == 200
    assert semester.json()["averaging_mode"] == "all_grades"
    assert client.get(f"/api/semesters/{semester_id}").json()["grading_scale"] == 100
    assert client.get(f"/api/semesters/{semester_id}").json()["name"] == "Весна"

    assert client.delete("/api/students/me").status_code == 204
    assert client.post("/api/students", json={"display_name": "Новый профиль"}).status_code == 201
    assert client.get("/api/semesters").json() == []
    assert client.get(f"/api/semesters/{semester_id}").status_code == 404


def test_subject_crud_and_grade_cascade(client, session):
    semester_id = create_semester(client)
    subject_id = create_subject(client, semester_id)
    subject_path = f"/api/subjects/{subject_id}"
    assert client.get(f"/api/subjects?semester_id={semester_id}").json() == [
        {"id": subject_id, "semester_id": semester_id, "name": "Математика"}
    ]
    assert client.get(subject_path).json()["name"] == "Математика"
    update = client.patch(subject_path, json={"name": "Алгебра"})
    assert update.status_code == 200
    assert update.json()["name"] == "Алгебра"

    grade = client.post("/api/grades", json={"subject_id": subject_id, "value": 5})
    assert grade.status_code == 201
    grade_id = grade.json()["id"]
    assert client.get(f"/api/grades/{grade_id}").status_code == 200

    assert client.delete(subject_path).status_code == 204
    assert client.get(subject_path).status_code == 404
    assert client.get(f"/api/grades/{grade_id}").status_code == 404
    count = session.scalar(text("SELECT count(*) FROM grades WHERE id = :id"), {"id": grade_id})
    assert count == 0


@pytest.mark.parametrize(("scale", "minimum"), [(5, 1), (12, 1), (100, 0)])
def test_grade_create_edit_delete_and_scale_boundaries(client, scale, minimum):
    semester_id = create_semester(client, scale=scale)
    subject_id = create_subject(client, semester_id)
    grade_response = client.post("/api/grades", json={"subject_id": subject_id, "value": minimum})
    assert grade_response.status_code == 201
    grade = grade_response.json()
    assert grade["value"] == minimum
    assert grade["grading_scale"] == scale

    grade_path = f"/api/grades/{grade['id']}"
    edited = client.patch(grade_path, json={"value": scale})
    assert edited.status_code == 200
    assert edited.json()["value"] == scale

    for invalid in (minimum - 1, scale + 1, "3", 3.5, True):
        assert client.post("/api/grades", json={"subject_id": subject_id, "value": invalid}).status_code == 422
        assert client.patch(grade_path, json={"value": invalid}).status_code == 422

    assert client.get(f"/api/grades?subject_id={subject_id}").json() == [edited.json()]
    other_scale = 12 if scale == 5 else 5
    assert client.patch(f"/api/semesters/{semester_id}", json={"grading_scale": other_scale}).status_code == 409
    assert client.delete(grade_path).status_code == 204
    assert client.patch(f"/api/semesters/{semester_id}", json={"grading_scale": other_scale}).status_code == 200


def test_scholarship_settings_replace_and_protect_grading_scale(client):
    semester_id = create_semester(client)
    url = f"/api/semesters/{semester_id}/scholarship-settings"
    assert client.get(url).status_code == 404
    for invalid in (0, "0.99", 5.01, "4.123"):
        assert client.put(url, json={"target_average": invalid}).status_code == 422

    target = client.put(url, json={"target_average": "4.40"})
    assert target.status_code == 201
    assert float(target.json()["target_average"]) == 4.4
    assert client.get(url).json() == target.json()
    updated = client.put(url, json={"target_average": 4.7})
    assert updated.status_code == 200
    assert updated.json()["target_average"] == "4.70"
    assert client.get(url).json() == updated.json()
    assert client.patch(f"/api/semesters/{semester_id}", json={"grading_scale": 12}).status_code == 409
    assert client.delete(url).status_code == 204
    assert client.get(url).status_code == 404
    assert client.patch(f"/api/semesters/{semester_id}", json={"grading_scale": 100}).status_code == 200
    assert client.put(url, json={"target_average": "0.01"}).status_code == 201


def test_unknown_resources_return_404(client):
    semester_id = create_semester(client)
    for url, patch in (
        ("/api/semesters/9999", {"name": "Пропавший семестр"}),
        ("/api/subjects/9999", {"name": "Пропавший предмет"}),
        ("/api/grades/9999", {"value": 4}),
    ):
        assert client.get(url).status_code == 404
        assert client.patch(url, json=patch).status_code == 404
        assert client.delete(url).status_code == 404

    assert client.get("/api/subjects?semester_id=9999").status_code == 404
    assert client.get("/api/grades?subject_id=9999").status_code == 404
    assert client.post("/api/grades", json={"subject_id": 9999, "value": 4}).status_code == 404
    assert client.post("/api/subjects", json={"semester_id": 9999, "name": "Алгебра"}).status_code == 404
    assert client.get(f"/api/semesters/{semester_id}").status_code == 200


def test_identifiers_outside_postgres_integer_range_return_422(client):
    create_semester(client)
    outside_range = 2**31
    assert client.get(f"/api/semesters/{outside_range}").status_code == 422
    assert client.get(f"/api/subjects?semester_id={outside_range}").status_code == 422
    assert client.post(
        "/api/subjects", json={"semester_id": outside_range, "name": "Алгебра"}
    ).status_code == 422
