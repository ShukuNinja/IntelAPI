from uuid import uuid4


def _project_id(client) -> str:
    response = client.post("/api/v1/projects", json={"name": f"env-tests-{uuid4()}"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_environment_crud_and_secret_is_not_returned(authenticated_client) -> None:
    client = authenticated_client
    project_id = _project_id(client)
    created = client.post(
        f"/api/v1/projects/{project_id}/environments",
        json={"name": " staging ", "base_url": "https://example.com"},
    )
    assert created.status_code == 201, created.text
    environment_id = created.json()["id"]

    plain = client.put(
        f"/api/v1/environments/{environment_id}/variables/API_VERSION",
        json={"value": "v1", "is_secret": False},
    )
    assert plain.status_code == 200, plain.text
    assert plain.json()["value"] == "v1"

    secret_value = f"secret-{uuid4()}"
    secret = client.put(
        f"/api/v1/environments/{environment_id}/variables/API_TOKEN",
        json={"value": secret_value, "is_secret": True},
    )
    assert secret.status_code == 200, secret.text
    assert secret.json()["value"] is None
    assert secret_value not in secret.text

    detail = client.get(f"/api/v1/environments/{environment_id}")
    assert detail.status_code == 200, detail.text
    values = {item["key"]: item for item in detail.json()["variables"]}
    assert values["API_VERSION"]["value"] == "v1"
    assert values["API_TOKEN"]["value"] is None
    assert secret_value not in detail.text


def test_environment_duplicate_name_conflicts(authenticated_client) -> None:
    client = authenticated_client
    project_id = _project_id(client)
    payload = {"name": "staging", "base_url": "https://example.com"}
    first = client.post(f"/api/v1/projects/{project_id}/environments", json=payload)
    assert first.status_code == 201, first.text
    second = client.post(f"/api/v1/projects/{project_id}/environments", json=payload)
    assert second.status_code == 409, second.text


def test_environment_variable_key_validation(authenticated_client) -> None:
    client = authenticated_client
    project_id = _project_id(client)
    environment = client.post(
        f"/api/v1/projects/{project_id}/environments",
        json={"name": "test", "base_url": "https://example.com"},
    )
    assert environment.status_code == 201, environment.text
    response = client.put(
        f"/api/v1/environments/{environment.json()['id']}/variables/INVALID-KEY",
        json={"value": "x", "is_secret": False},
    )
    assert response.status_code == 422, response.text
