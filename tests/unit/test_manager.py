import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from sandbox_manager.manager import SandboxManager, QuotaExceededError
from database.models import Sandbox, SandboxStatus, NetworkPolicy
from runtimes.base import ExecResult


class MockRuntime:
    async def create(self, config):
        return "mock-container-id"

    async def exec(self, container_id, command, args, timeout_seconds):
        return ExecResult(exit_code=0, stdout="4\n", stderr="", duration_ms=50)

    async def destroy(self, container_id):
        pass

    async def pause(self, container_id):
        pass

    async def resume(self, container_id):
        pass

    async def logs(self, container_id, tail=100):
        return "some logs"

    async def is_running(self, container_id):
        return True

    async def fork(self, source_id, config):
        return "forked-container-id"


class MockDB:
    def __init__(self, sandboxes=None):
        self._sandboxes = sandboxes or []
        self._added = []
        self._committed = False

    def add(self, obj):
        self._added.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        self._committed = True

    async def rollback(self):
        pass

    async def execute(self, stmt):
        result = MagicMock()
        result.scalars.return_value.all.return_value = self._sandboxes
        result.scalar_one_or_none.return_value = self._sandboxes[0] if self._sandboxes else None
        return result


@pytest.mark.asyncio
async def test_create_sandbox_success():
    db = MockDB()
    manager = SandboxManager(runtime=MockRuntime(), db=db)
    sandbox = await manager.create_sandbox(
        user_id="user1",
        template="python",
        ttl_seconds=300,
        cpu_limit=1.0,
        memory_mb=512,
    )
    assert sandbox.status == SandboxStatus.READY
    assert sandbox.container_id == "mock-container-id"


@pytest.mark.asyncio
async def test_create_sandbox_quota_exceeded():
    existing = [MagicMock() for _ in range(5)]
    db = MockDB(sandboxes=existing)
    manager = SandboxManager(runtime=MockRuntime(), db=db)
    with pytest.raises(QuotaExceededError):
        await manager.create_sandbox(
            user_id="user1",
            template="python",
            ttl_seconds=300,
            cpu_limit=1.0,
            memory_mb=512,
        )


@pytest.mark.asyncio
async def test_exec_success():
    now = datetime.utcnow()
    sandbox = Sandbox(
        id="sandbox-1",
        user_id="user1",
        status=SandboxStatus.READY,
        template="python",
        created_at=now,
        expires_at=now + timedelta(seconds=300),
        cpu_limit=1.0,
        memory_limit=512,
        container_id="mock-container-id",
        network_policy=NetworkPolicy.RESTRICTED,
    )
    db = MockDB(sandboxes=[sandbox])
    manager = SandboxManager(runtime=MockRuntime(), db=db)
    execution = await manager.exec_in_sandbox(
        sandbox_id="sandbox-1",
        user_id="user1",
        command="python",
        args=["-c", "print(2+2)"],
        timeout_seconds=10,
    )
    assert execution.exit_code == 0
    assert execution.stdout == "4\n"
