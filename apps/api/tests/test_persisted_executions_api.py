from uuid import uuid4

import httpx


def _create_project(client) -> str:
    response = client.post(
        "/api/v1/projects",
        json={"name": f"execution-tests-{uuid4()}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_saved_request(client, project_id: str) -> str:
    response = client.post(
        f"/api/v1/projects/{project_id}/requests",
        json={
            "name": "Example GET",
            "method": "GET",
            "url_template": "https://example.com/api/health",
            "headers": {},
            "query_params": {},
            "body": None,
            "body_type": "none",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_execute_saved_request_persists_response_and_history(
    authenticated_client,
    monkeypatch,
):
    class FakeResponse:
        status_code = 200
        headers = {
            "content-type": "application/json",
            "set-cookie": "must-not-be-retained",
        }
        encoding = "utf-8"

        def iter_bytes(self):
            yield b'{"ok":true}'

    class FakeStream:
        def __enter__(self):
            return FakeResponse()

        def __exit__(self, *args):
            return False

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, *args, **kwargs):
            return FakeStream()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    client = authenticated_client
    project_id = _create_project(client)
    request_id = _create_saved_request(client, project_id)

    executed = client.post(
        f"/api/v1/requests/{request_id}/execute",
        json={},
    )
    assert executed.status_code == 201, executed.text

    execution = executed.json()
    execution_id = execution["id"]

    assert execution["status"] == "completed"
    assert execution["method"] == "GET"
    assert execution["response_status_code"] == 200
    assert execution["response_body"] == '{"ok":true}'
    assert "set-cookie" not in execution["response_headers"]

    detail = client.get(f"/api/v1/executions/{execution_id}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["id"] == execution_id

    history = client.get(f"/api/v1/projects/{project_id}/executions")
    assert history.status_code == 200, history.text
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["id"] == execution_id


def test_execution_cannot_be_read_by_another_user(
    two_authenticated_clients,
    monkeypatch,
):
    class FakeResponse:
        status_code = 200
        headers = {"content-type": "application/json"}
        encoding = "utf-8"

        def iter_bytes(self):
            yield b'{"ok":true}'

    class FakeStream:
        def __enter__(self):
            return FakeResponse()

        def __exit__(self, *args):
            return False

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def stream(self, *args, **kwargs):
            return FakeStream()

    monkeypatch.setattr(httpx, "Client", FakeClient)

    owner, other_user = two_authenticated_clients
    project_id = _create_project(owner)
    request_id = _create_saved_request(owner, project_id)

    executed = owner.post(
        f"/api/v1/requests/{request_id}/execute",
        json={},
    )
    assert executed.status_code == 201, executed.text

    execution_id = executed.json()["id"]

    response = other_user.get(f"/api/v1/executions/{execution_id}")
    assert response.status_code == 404
