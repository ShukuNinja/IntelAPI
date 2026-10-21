from uuid import uuid4

import pytest

BASE_URL = "/api/v1"


def create_project(client, name="Saved Requests Test Project"):
    response = client.post(
        f"{BASE_URL}/projects",
        json={"name": name, "description": "Test project"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_collection(client, project_id, name="Test Collection"):
    response = client.post(
        f"{BASE_URL}/projects/{project_id}/collections",
        json={"name": name, "description": "Collection for saved requests"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_saved_request(
    client,
    project_id,
    *,
    name="Get Example",
    collection_id=None,
    environment_id=None,
):
    payload = {
        "name": name,
        "method": "GET",
        "url_template": "https://example.com/api/items",
        "headers": {"Accept": "application/json"},
        "query_params": {"limit": "10"},
        "body": None,
        "body_type": "none",
    }

    if collection_id is not None:
        payload["collection_id"] = collection_id

    if environment_id is not None:
        payload["environment_id"] = environment_id

    response = client.post(
        f"{BASE_URL}/projects/{project_id}/requests",
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_saved_request(authenticated_client):
    project = create_project(authenticated_client)
    collection = create_collection(authenticated_client, project["id"])

    response = authenticated_client.post(
        f"{BASE_URL}/projects/{project['id']}/requests",
        json={
            "name": "Create Item",
            "method": "POST",
            "url_template": "https://example.com/api/items",
            "collection_id": collection["id"],
            "headers": {"Content-Type": "application/json"},
            "query_params": {},
            "body": {"name": "Example"},
            "body_type": "json",
        },
    )

    assert response.status_code == 201, response.text
    data = response.json()

    assert data["name"] == "Create Item"
    assert data["method"] == "POST"
    assert data["project_id"] == project["id"]
    assert data["collection_id"] == collection["id"]
    assert data["url_template"] == "https://example.com/api/items"
    assert data["headers"] == {"Content-Type": "application/json"}
    assert data["body"] == {"name": "Example"}
    assert data["body_type"] == "json"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data
    assert "auth_config" not in data


def test_list_saved_requests_with_pagination(authenticated_client):
    project = create_project(authenticated_client)

    create_saved_request(authenticated_client, project["id"], name="Request A")
    create_saved_request(authenticated_client, project["id"], name="Request B")

    response = authenticated_client.get(
        f"{BASE_URL}/projects/{project['id']}/requests",
        params={"limit": 1, "offset": 0},
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert len(data["items"]) == 1
    assert data["pagination"]["limit"] == 1
    assert data["pagination"]["offset"] == 0
    assert data["pagination"]["total"] == 2


def test_list_saved_requests_filters_by_collection(authenticated_client):
    project = create_project(authenticated_client)
    first_collection = create_collection(
        authenticated_client, project["id"], name="First Collection"
    )
    second_collection = create_collection(
        authenticated_client, project["id"], name="Second Collection"
    )

    create_saved_request(
        authenticated_client,
        project["id"],
        name="First Request",
        collection_id=first_collection["id"],
    )
    create_saved_request(
        authenticated_client,
        project["id"],
        name="Second Request",
        collection_id=second_collection["id"],
    )

    response = authenticated_client.get(
        f"{BASE_URL}/projects/{project['id']}/requests",
        params={"collection_id": first_collection["id"]},
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert len(data["items"]) == 1
    assert data["items"][0]["name"] == "First Request"
    assert data["items"][0]["collection_id"] == first_collection["id"]
    assert data["pagination"]["total"] == 1


def test_get_saved_request(authenticated_client):
    project = create_project(authenticated_client)
    saved_request = create_saved_request(authenticated_client, project["id"])

    response = authenticated_client.get(f"{BASE_URL}/requests/{saved_request['id']}")

    assert response.status_code == 200, response.text
    assert response.json()["id"] == saved_request["id"]
    assert response.json()["name"] == "Get Example"


def test_update_saved_request(authenticated_client):
    project = create_project(authenticated_client)
    saved_request = create_saved_request(authenticated_client, project["id"])

    response = authenticated_client.patch(
        f"{BASE_URL}/requests/{saved_request['id']}",
        json={
            "name": "Updated Request",
            "method": "PATCH",
            "url_template": "https://example.com/api/items/1",
            "headers": {"Accept": "application/json"},
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()

    assert data["id"] == saved_request["id"]
    assert data["name"] == "Updated Request"
    assert data["method"] == "PATCH"
    assert data["url_template"] == "https://example.com/api/items/1"


def test_update_saved_request_can_clear_collection(authenticated_client):
    project = create_project(authenticated_client)
    collection = create_collection(authenticated_client, project["id"])
    saved_request = create_saved_request(
        authenticated_client,
        project["id"],
        collection_id=collection["id"],
    )

    response = authenticated_client.patch(
        f"{BASE_URL}/requests/{saved_request['id']}",
        json={"collection_id": None},
    )

    assert response.status_code == 200, response.text
    assert response.json()["collection_id"] is None


def test_delete_saved_request(authenticated_client):
    project = create_project(authenticated_client)
    saved_request = create_saved_request(authenticated_client, project["id"])

    response = authenticated_client.delete(f"{BASE_URL}/requests/{saved_request['id']}")

    assert response.status_code == 204

    get_response = authenticated_client.get(f"{BASE_URL}/requests/{saved_request['id']}")
    assert get_response.status_code == 404


def test_get_unknown_saved_request_returns_404(authenticated_client):
    response = authenticated_client.get(f"{BASE_URL}/requests/{uuid4()}")

    assert response.status_code == 404


def test_create_request_rejects_unknown_collection(authenticated_client):
    project = create_project(authenticated_client)

    response = authenticated_client.post(
        f"{BASE_URL}/projects/{project['id']}/requests",
        json={
            "name": "Invalid Collection Request",
            "method": "GET",
            "url_template": "https://example.com",
            "collection_id": str(uuid4()),
        },
    )

    assert response.status_code == 422


def test_create_request_rejects_collection_from_another_project(
    authenticated_client,
):
    first_project = create_project(authenticated_client, name="First Project")
    second_project = create_project(authenticated_client, name="Second Project")
    collection = create_collection(authenticated_client, first_project["id"])

    response = authenticated_client.post(
        f"{BASE_URL}/projects/{second_project['id']}/requests",
        json={
            "name": "Cross-Project Request",
            "method": "GET",
            "url_template": "https://example.com",
            "collection_id": collection["id"],
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "forbidden_header",
    [
        "Host",
        "Content-Length",
        "Connection",
        "Transfer-Encoding",
        "Cookie",
        "Proxy-Authorization",
    ],
)
def test_create_request_rejects_forbidden_headers(authenticated_client, forbidden_header):
    project = create_project(authenticated_client)

    response = authenticated_client.post(
        f"{BASE_URL}/projects/{project['id']}/requests",
        json={
            "name": "Unsafe Header Request",
            "method": "GET",
            "url_template": "https://example.com",
            "headers": {forbidden_header: "unsafe-value"},
        },
    )

    assert response.status_code == 422


def test_create_request_rejects_body_when_body_type_is_none(
    authenticated_client,
):
    project = create_project(authenticated_client)

    response = authenticated_client.post(
        f"{BASE_URL}/projects/{project['id']}/requests",
        json={
            "name": "Invalid Body Request",
            "method": "POST",
            "url_template": "https://example.com",
            "body": {"unexpected": True},
            "body_type": "none",
        },
    )

    assert response.status_code == 422


def test_patch_rejects_empty_payload(authenticated_client):
    project = create_project(authenticated_client)
    saved_request = create_saved_request(authenticated_client, project["id"])

    response = authenticated_client.patch(
        f"{BASE_URL}/requests/{saved_request['id']}",
        json={},
    )

    assert response.status_code == 422


def test_patch_rejects_null_required_fields(authenticated_client):
    project = create_project(authenticated_client)
    saved_request = create_saved_request(authenticated_client, project["id"])

    for field in ("name", "method", "url_template", "headers", "query_params", "body_type"):
        response = authenticated_client.patch(
            f"{BASE_URL}/requests/{saved_request['id']}",
            json={field: None},
        )
        assert response.status_code == 422, f"{field} unexpectedly accepted null: {response.text}"


def test_request_response_does_not_expose_auth_config(
    authenticated_client,
):
    project = create_project(authenticated_client)
    saved_request = create_saved_request(authenticated_client, project["id"])

    response = authenticated_client.get(f"{BASE_URL}/requests/{saved_request['id']}")

    assert response.status_code == 200, response.text
    assert "auth_config" not in response.json()


def test_other_user_cannot_access_saved_request(authenticated_client):
    from uuid import uuid4

    from fastapi.testclient import TestClient

    from app.api.auth.sessions import create_session
    from app.core.config import get_settings
    from app.db.session import get_db
    from app.main import app
    from app.models.user import User

    # The existing fixture owns the database transaction and dependency
    # override. Reuse its overridden DB session for both users.
    db_dependency = app.dependency_overrides[get_db]
    db_generator = db_dependency()
    db = next(db_generator)

    try:
        second_user = User(
            google_sub=f"test-user-{uuid4()}",
            email=f"{uuid4()}@example.com",
            display_name="Second Test User",
        )
        db.add(second_user)
        db.flush()

        second_token, _ = create_session(db, second_user.id)

        settings = get_settings()
        second_csrf = "second-user-csrf-token"

        # Create the second client while keeping the first client's session.
        with TestClient(
            app,
            base_url="http://localhost:8000",
            headers={
                "Origin": "http://localhost:8000",
                "X-CSRF-Token": second_csrf,
            },
        ) as second_client:
            second_client.cookies.set(
                settings.session_cookie_name,
                second_token,
            )
            second_client.cookies.set("csrf_token", second_csrf)

            project = create_project(authenticated_client)
            saved_request = create_saved_request(
                authenticated_client,
                project["id"],
                name="Private Request",
            )
            request_id = saved_request["id"]

            response = second_client.get(f"{BASE_URL}/requests/{request_id}")
            assert response.status_code == 404, response.text

            response = second_client.patch(
                f"{BASE_URL}/requests/{request_id}",
                json={"name": "Unauthorized Update"},
            )
            assert response.status_code == 404, response.text

            response = second_client.delete(f"{BASE_URL}/requests/{request_id}")
            assert response.status_code == 404, response.text

            response = authenticated_client.get(f"{BASE_URL}/requests/{request_id}")
            assert response.status_code == 200, response.text
            assert response.json()["name"] == "Private Request"

    finally:
        # Close the generator without closing the fixture-owned session.
        db_generator.close()
