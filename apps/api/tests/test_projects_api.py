from uuid import uuid4


def test_delete_project_removes_it_from_active_list_but_retains_archive(
    authenticated_client,
) -> None:
    client = authenticated_client
    created = client.post("/api/v1/projects", json={"name": f"delete-{uuid4()}"})
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]

    deleted = client.delete(f"/api/v1/projects/{project_id}")

    assert deleted.status_code == 204
    active = client.get("/api/v1/projects").json()["items"]
    archived = client.get("/api/v1/projects?include_archived=true").json()["items"]
    assert all(project["id"] != project_id for project in active)
    archived_project = next(project for project in archived if project["id"] == project_id)
    assert archived_project["archived_at"] is not None
    assert client.delete(f"/api/v1/projects/{project_id}").status_code == 404


def test_delete_project_is_owner_checked(two_authenticated_clients) -> None:
    owner, other = two_authenticated_clients
    created = owner.post("/api/v1/projects", json={"name": f"private-delete-{uuid4()}"})
    project_id = created.json()["id"]

    response = other.delete(f"/api/v1/projects/{project_id}")

    assert response.status_code == 404
