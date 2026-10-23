from uuid import uuid4

SPEC = """
openapi: 3.1.0
info:
  title: Experiment API
  version: "1.0"
paths:
  /items:
    get:
      summary: List items
      responses:
        "200":
          description: OK
          content:
            application/json:
              schema:
                type: object
                required: [items]
                properties:
                  items:
                    type: array
"""


def _setup(client):
    project = client.post("/api/v1/projects", json={"name": f"experiment-{uuid4()}"})
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]
    specification = client.post(
        f"/api/v1/projects/{project_id}/specifications/import", json={"content": SPEC}
    )
    assert specification.status_code == 201, specification.text
    operation = client.get(
        f"/api/v1/specifications/{specification.json()['id']}/operations"
    ).json()["items"][0]
    environment = client.post(
        f"/api/v1/projects/{project_id}/environments",
        json={"name": "Experiment target", "base_url": "https://example.com"},
    )
    assert environment.status_code == 201, environment.text
    return project_id, operation["id"], environment.json()["id"]


def test_comparative_experiment_persists_four_real_approach_campaigns(authenticated_client):
    client = authenticated_client
    project_id, operation_id, environment_id = _setup(client)

    created = client.post(
        f"/api/v1/projects/{project_id}/experiments",
        json={
            "name": "Four policy comparison",
            "operation_ids": [operation_id],
            "environment_id": environment_id,
            "approaches": [
                "llm_baseline",
                "semantic_assisted",
                "feedback_guided",
                "evidence_backed",
            ],
            "use_llm": False,
        },
    )
    assert created.status_code == 202, created.text
    experiment = created.json()
    assert experiment["state"] == "queued"
    assert len(experiment["runs"]) == 4
    assert {run["approach"] for run in experiment["runs"]} == {
        "llm_baseline",
        "semantic_assisted",
        "feedback_guided",
        "evidence_backed",
    }
    assert all(run["candidate_count"] > 0 for run in experiment["runs"])
    assert all(run["state"] == "queued" for run in experiment["runs"])

    comparison = client.get(f"/api/v1/experiments/{experiment['id']}/comparison")
    assert comparison.status_code == 200, comparison.text
    metrics = comparison.json()["metrics_by_approach"]
    assert metrics["llm_baseline"]["candidate_validity_rate"]["value"] is None
    assert metrics["llm_baseline"]["endpoint_coverage"]["value"] == 0
    assert metrics["semantic_assisted"]["constraint_coverage"]["unavailable_reason"]


def test_experiment_resources_are_owner_checked(two_authenticated_clients):
    owner, other = two_authenticated_clients
    project_id, operation_id, environment_id = _setup(owner)
    created = owner.post(
        f"/api/v1/projects/{project_id}/experiments",
        json={
            "name": "Private experiment",
            "operation_ids": [operation_id],
            "environment_id": environment_id,
            "approaches": ["feedback_guided"],
        },
    )
    assert created.status_code == 202, created.text
    experiment_id = created.json()["id"]

    assert other.get(f"/api/v1/experiments/{experiment_id}").status_code == 404
    assert other.get(f"/api/v1/experiments/{experiment_id}/comparison").status_code == 404
    assert other.get(f"/api/v1/projects/{project_id}/experiments").status_code == 404
