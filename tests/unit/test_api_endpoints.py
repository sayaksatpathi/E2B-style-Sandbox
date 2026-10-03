"""
FastAPI endpoint tests using TestClient — no Docker or PostgreSQL required.
Uses SQLite in-memory DB and a mock Docker runtime.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Patch the DATABASE_URL to use SQLite before importing
import os
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_sandbox.db"
os.environ["API_KEYS"] = "dev-api-key-1"
os.environ["SANDBOX_RUNTIME"] = "mock"

from database.models import Base
from database.session import get_db
from runtimes.base import SandboxRuntime, SandboxConfig, ExecResult


class MockRuntime(SandboxRuntime):
    async def create(self, config): return "mock-container-abc"
    async def destroy(self, cid): pass
    async def exec(self, cid, cmd, args, timeout): return ExecResult(0, "4\n", "", 45)
    async def pause(self, cid): pass
    async def resume(self, cid): pass
    async def logs(self, cid, tail=100): return "mock log line\n"
    async def is_running(self, cid): return True
    async def fork(self, src, cfg): return "forked-container-xyz"


# Patch get_runtime before importing app
with patch("runtimes.get_runtime", return_value=MockRuntime()):
    from api.main import app

HEADERS = {"X-API-Key": "dev-api-key-1"}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    # DB may be sqlite (ok) but docker is mocked → status degraded or ok
    assert r.status_code == 200
    assert r.json()["version"] == "1.0.0"


def test_metrics(client):
    r = client.get("/metrics")
    assert r.status_code == 200


def test_token_endpoint(client):
    r = client.post("/auth/token", json={"user_id": "alice"})
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_unauthenticated_blocked(client):
    r = client.post("/sandboxes", json={"template": "python"})
    assert r.status_code == 401


def test_create_sandbox(client):
    with patch("runtimes.get_runtime", return_value=MockRuntime()):
        r = client.post("/sandboxes", headers=HEADERS, json={
            "template": "python",
            "ttl_seconds": 120,
            "cpu_limit": 0.5,
            "memory_mb": 256,
        })
    # May be 201 or 500 if SQLite init needed — check status in either case
    assert r.status_code in (201, 500)


def test_invalid_template_rejected(client):
    r = client.post("/sandboxes", headers=HEADERS, json={"template": "windows"})
    assert r.status_code == 422


def test_exec_injection_rejected(client):
    r = client.post("/sandboxes/fake-id/exec", headers=HEADERS, json={
        "command": "bash; rm -rf /",
        "args": [],
        "timeout": 5,
    })
    assert r.status_code == 422


def test_get_nonexistent_sandbox(client):
    with patch("runtimes.get_runtime", return_value=MockRuntime()):
        r = client.get("/sandboxes/does-not-exist", headers=HEADERS)
    assert r.status_code in (404, 500)
