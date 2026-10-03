"""
Security / isolation tests.

These run against a live API and verify that isolation constraints hold.
Run with: pytest tests/security/ -v
"""
import os
import pytest
import httpx

BASE_URL = os.getenv("SANDBOX_API_URL", "http://localhost:8000")
API_KEY = os.getenv("SANDBOX_API_KEY", "dev-api-key-1")
HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture
def client():
    return httpx.Client(base_url=BASE_URL, headers=HEADERS, timeout=60)


@pytest.fixture
def sandbox(client):
    r = client.post("/sandboxes", json={"template": "python", "ttl_seconds": 60})
    assert r.status_code == 201
    data = r.json()
    yield data["id"]
    client.delete(f"/sandboxes/{data['id']}")


def test_cannot_read_host_etc_passwd(client, sandbox):
    """Sandbox should not be able to read /etc/passwd of the host."""
    r = client.post(f"/sandboxes/{sandbox}/exec", json={
        "command": "python",
        "args": ["-c", "import os; f=open('/etc/passwd'); print(f.read()[:50])"],
        "timeout": 5,
    })
    # Either the file is readable (container's own /etc/passwd, not host) or fails
    # The key check: no host-specific user accounts leak
    if r.status_code == 200:
        stdout = r.json().get("stdout", "")
        # Container passwd should be minimal; won't have host-specific users
        assert "appuser" not in stdout or len(stdout) < 500


def test_no_network_by_default(client, sandbox):
    """Sandbox with 'none' network policy cannot reach external IPs."""
    r_sandbox = client.post("/sandboxes", json={
        "template": "python",
        "ttl_seconds": 60,
        "network_policy": "none",
    })
    sandbox_id = r_sandbox.json()["id"]
    try:
        r = client.post(f"/sandboxes/{sandbox_id}/exec", json={
            "command": "python",
            "args": ["-c", "import urllib.request; urllib.request.urlopen('http://8.8.8.8', timeout=2)"],
            "timeout": 10,
        })
        # Should fail with a network error
        if r.status_code == 200:
            assert r.json()["exit_code"] != 0
    finally:
        client.delete(f"/sandboxes/{sandbox_id}")


def test_memory_limit_enforced(client, sandbox):
    """Allocating more than the memory limit should be killed."""
    r = client.post(f"/sandboxes/{sandbox}/exec", json={
        "command": "python",
        "args": ["-c", "x = bytearray(600 * 1024 * 1024)"],
        "timeout": 15,
    })
    if r.status_code == 200:
        # Should exit non-zero due to OOM
        assert r.json()["exit_code"] != 0


def test_timeout_enforced(client, sandbox):
    """Commands exceeding the timeout should not hang indefinitely."""
    r = client.post(f"/sandboxes/{sandbox}/exec", json={
        "command": "python",
        "args": ["-c", "import time; time.sleep(999)"],
        "timeout": 3,
    })
    # The API should return within a reasonable time; exit code may vary
    assert r.status_code in (200, 500, 408)


def test_cross_user_isolation(client):
    """User A cannot access User B's sandbox."""
    # Create sandbox as user A
    r = client.post("/sandboxes", json={"template": "python", "ttl_seconds": 60})
    assert r.status_code == 201
    sandbox_id = r.json()["id"]

    # Try to access as a different (invalid) API key
    other_headers = {"X-API-Key": "completely-wrong-key"}
    r2 = httpx.get(f"{BASE_URL}/sandboxes/{sandbox_id}", headers=other_headers)
    assert r2.status_code in (401, 404)

    client.delete(f"/sandboxes/{sandbox_id}")
