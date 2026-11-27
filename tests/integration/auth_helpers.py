def register_and_login(client, username="student", name="Student"):
    credentials = {"username": username, "password": "test-password-123"}
    response = client.post("/api/auth/register", json={**credentials, "display_name": name})
    assert response.status_code == 201, response.text
    response = client.post("/api/auth/login", json=credentials)
    assert response.status_code == 200, response.text
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
