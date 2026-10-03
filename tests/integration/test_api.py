"""
Integration tests — require a running API (docker-compose up).
Run with: pytest tests/integration/ -v
"""
import os
import pytest
import httpx

BASE_URL = os.getenv("SANDBOX_API_URL", "http://localhost:8000")
API_KEY = os.getenv("SANDBOX_API_KEY", "dev-api-key-1")
HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture(scope="module")
def client():
    return httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=60)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("ok", "degraded")


def test_metrics(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert b"sandboxes_created_total" in r.content or "sandboxes_created_total" in r.text


@pytest.fixture(scope="module")
def sandbox_id(client):
    r = client.post("/sandboxes", json={
        "template": "python",
        "ttl_seconds": 120,
        "cpu_limit": 0.5,
        "memory_mb": 256,
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_create_sandbox(client):
    r = client.post("/sandboxes", json={"template": "python", "ttl_seconds": 120})
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "READY"
    # cleanup
    client.delete(f"/sandboxes/{data['id']}")


def test_get_sandbox(client, sandbox_id):
    r = client.get(f"/sandboxes/{sandbox_id}")
    assert r.status_code == 200
    assert r.json()["id"] == sandbox_id


def test_exec_python(client, sandbox_id):
    r = client.post(f"/sandboxes/{sandbox_id}/exec", json={
        "command": "python",
        "args": ["-c", "print(2+2)"],
        "timeout": 10,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["exit_code"] == 0
    assert "4" in data["stdout"]


def test_exec_rejected_injection(client, sandbox_id):
    r = client.post(f"/sandboxes/{sandbox_id}/exec", json={
        "command": "bash; rm -rf /",
        "args": [],
        "timeout": 5,
    })
    assert r.status_code == 422


def test_get_logs(client, sandbox_id):
    r = client.get(f"/sandboxes/{sandbox_id}/logs")
    assert r.status_code == 200


def test_pause_resume(client, sandbox_id):
    r = client.post(f"/sandboxes/{sandbox_id}/pause")
    assert r.status_code in (204, 409)
    r = client.post(f"/sandboxes/{sandbox_id}/resume")
    assert r.status_code in (204, 409)


def test_delete_sandbox(client, sandbox_id):
    r = client.delete(f"/sandboxes/{sandbox_id}")
    assert r.status_code == 204


def test_unauthenticated():
    r = httpx.get(f"{BASE_URL}/sandboxes")
    assert r.status_code == 401
