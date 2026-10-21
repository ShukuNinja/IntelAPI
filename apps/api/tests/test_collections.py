from uuid import uuid4

from fastapi.testclient import TestClient


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/v1/projects",
        json={"name": f"Collection Test {uuid4()}"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_create_and_list_collections(
    authenticated_client: TestClient,
) -> None:
    project_id = _create_project(authenticated_client)

    create_response = authenticated_client.post(
        f"/api/v1/projects/{project_id}/collections",
        json={"name": "  Requests  ", "description": "API requests"},
    )

    assert create_response.status_code == 201, create_response.text
    created = create_response.json()
    assert created["name"] == "Requests"
    assert created["description"] == "API requests"
    assert created["project_id"] == project_id

    list_response = authenticated_client.get(
        f"/api/v1/projects/{project_id}/collections",
    )

    assert list_response.status_code == 200, list_response.text
    result = list_response.json()
    assert result["pagination"]["total"] == 1
    assert result["pagination"]["limit"] == 50
    assert len(result["items"]) == 1
    assert result["items"][0]["id"] == created["id"]


def test_duplicate_collection_name_returns_conflict(
    authenticated_client: TestClient,
) -> None:
    project_id = _create_project(authenticated_client)
    url = f"/api/v1/projects/{project_id}/collections"

    first = authenticated_client.post(url, json={"name": "Requests"})
    second = authenticated_client.post(url, json={"name": "Requests"})

    assert first.status_code == 201, first.text
    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == "CONFLICT"


def test_collection_can_be_retrieved_updated_and_deleted(
    authenticated_client: TestClient,
) -> None:
    project_id = _create_project(authenticated_client)

    create_response = authenticated_client.post(
        f"/api/v1/projects/{project_id}/collections",
        json={"name": "Initial"},
    )
    assert create_response.status_code == 201, create_response.text
    collection_id = create_response.json()["id"]

    item_url = f"/api/v1/collections/{collection_id}"

    get_response = authenticated_client.get(item_url)
    assert get_response.status_code == 200, get_response.text
    assert get_response.json()["name"] == "Initial"

    update_response = authenticated_client.patch(
        item_url,
        json={"name": "Updated", "description": "Updated description"},
    )
    assert update_response.status_code == 200, update_response.text
    assert update_response.json()["name"] == "Updated"
    assert update_response.json()["description"] == "Updated description"

    delete_response = authenticated_client.delete(item_url)
    assert delete_response.status_code == 204, delete_response.text

    missing_response = authenticated_client.get(item_url)
    assert missing_response.status_code == 404


def test_collection_routes_require_authentication() -> None:
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        response = client.get(
            f"/api/v1/projects/{uuid4()}/collections",
        )

    assert response.status_code == 401


def test_cannot_access_another_users_project_collections(
    authenticated_client: TestClient,
) -> None:
    # A random UUID does not belong to the authenticated user.
    response = authenticated_client.get(
        f"/api/v1/projects/{uuid4()}/collections",
    )

    assert response.status_code == 404
