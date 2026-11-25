from auth_helpers import register_and_login


def test_accounts_are_isolated(client):
    assert client.get("/api/semesters").status_code == 401
    register_and_login(client, "alice")
    semester = client.post("/api/semesters", json={"name": "Private", "grading_scale": 12})
    assert semester.status_code == 201
    sid = semester.json()["id"]
    subject = client.post("/api/subjects", json={"semester_id": sid, "name": "Math"}).json()
    grade = client.post("/api/grades", json={"subject_id": subject["id"], "value": 11}).json()
    register_and_login(client, "bob")
    assert client.get("/api/semesters").json() == []
    assert client.get(f"/api/semesters/{sid}").status_code == 404
    assert client.get(f"/api/subjects/{subject['id']}").status_code == 404
    assert client.get(f"/api/grades/{grade['id']}").status_code == 404
    assert client.get("/api/statistics", params={"semester_id": sid}).status_code == 404
    assert client.post("/api/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401
    client.headers["Authorization"] = "Bearer invalid"
    assert client.get("/api/students/me").status_code == 401
