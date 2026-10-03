import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from database.models import Sandbox, Execution, AuditLog, SandboxStatus, NetworkPolicy
from runtimes.base import SandboxRuntime, SandboxConfig
from observability.metrics import (
    SANDBOXES_CREATED, SANDBOXES_DESTROYED, SANDBOX_CREATION_FAILURES,
    SANDBOX_EXECUTIONS, SANDBOX_EXECUTION_FAILURES, SANDBOX_EXECUTION_DURATION,
    ACTIVE_SANDBOXES,
)

logger = logging.getLogger(__name__)


class QuotaExceededError(Exception):
    pass


class SandboxNotFoundError(Exception):
    pass


class SandboxManager:
    MAX_SANDBOXES_PER_USER = 5

    def __init__(self, runtime: SandboxRuntime, db: AsyncSession):
        self.runtime = runtime
        self.db = db

    async def create_sandbox(
        self,
        user_id: str,
        template: str,
        ttl_seconds: int,
        cpu_limit: float,
        memory_mb: int,
        network_policy: str = "restricted",
        pid_limit: int = 64,
        ip_address: str = None,
    ) -> Sandbox:
        # Enforce per-user quota
        result = await self.db.execute(
            select(Sandbox).where(
                Sandbox.user_id == user_id,
                Sandbox.status.notin_([SandboxStatus.DESTROYED, SandboxStatus.FAILED, SandboxStatus.EXPIRED]),
            )
        )
        active = result.scalars().all()
        if len(active) >= self.MAX_SANDBOXES_PER_USER:
            raise QuotaExceededError(
                f"User {user_id} has reached the maximum of {self.MAX_SANDBOXES_PER_USER} active sandboxes."
            )

        sandbox_id = str(uuid.uuid4())
        now = datetime.utcnow()
        expires_at = now + timedelta(seconds=ttl_seconds)

        sandbox = Sandbox(
            id=sandbox_id,
            user_id=user_id,
            status=SandboxStatus.CREATING,
            template=template,
            created_at=now,
            expires_at=expires_at,
            cpu_limit=cpu_limit,
            memory_limit=memory_mb,
            pid_limit=pid_limit,
            network_policy=NetworkPolicy(network_policy),
        )
        self.db.add(sandbox)
        await self.db.flush()

        try:
            config = SandboxConfig(
                sandbox_id=sandbox_id,
                template=template,
                cpu_limit=cpu_limit,
                memory_mb=memory_mb,
                pid_limit=pid_limit,
                network_policy=network_policy,
                ttl_seconds=ttl_seconds,
            )
            container_id = await self.runtime.create(config)
            sandbox.container_id = container_id
            sandbox.status = SandboxStatus.READY
            SANDBOXES_CREATED.labels(template=template).inc()
            ACTIVE_SANDBOXES.inc()
        except Exception as e:
            logger.error(f"Failed to create container for sandbox {sandbox_id}: {e}")
            sandbox.status = SandboxStatus.FAILED
            SANDBOX_CREATION_FAILURES.labels(error_type=type(e).__name__).inc()
            await self.db.commit()
            raise

        await self._audit(user_id, "CREATE_SANDBOX", sandbox_id, ip_address=ip_address)
        await self.db.commit()
        return sandbox

    async def list_sandboxes(self, user_id: str) -> list[Sandbox]:
        result = await self.db.execute(
            select(Sandbox)
            .where(Sandbox.user_id == user_id)
            .order_by(Sandbox.created_at.desc())
        )
        return result.scalars().all()

    async def get_sandbox(self, sandbox_id: str, user_id: str) -> Sandbox:
        result = await self.db.execute(
            select(Sandbox).where(Sandbox.id == sandbox_id, Sandbox.user_id == user_id)
        )
        sandbox = result.scalar_one_or_none()
        if not sandbox:
            raise SandboxNotFoundError(f"Sandbox {sandbox_id} not found.")
        return sandbox

    async def destroy_sandbox(self, sandbox_id: str, user_id: str, reason: str = "user", ip_address: str = None) -> None:
        sandbox = await self.get_sandbox(sandbox_id, user_id)
        if sandbox.status in (SandboxStatus.DESTROYED, SandboxStatus.DESTROYING):
            return

        sandbox.status = SandboxStatus.DESTROYING
        await self.db.flush()

        if sandbox.container_id:
            try:
                await self.runtime.destroy(sandbox.container_id)
            except Exception as e:
                logger.warning(f"Container destroy error for {sandbox_id}: {e}")

        sandbox.status = SandboxStatus.DESTROYED
        SANDBOXES_DESTROYED.labels(reason=reason).inc()
        ACTIVE_SANDBOXES.dec()
        await self._audit(user_id, "DESTROY_SANDBOX", sandbox_id, ip_address=ip_address)
        await self.db.commit()

    async def exec_in_sandbox(
        self,
        sandbox_id: str,
        user_id: str,
        command: str,
        args: list[str],
        timeout_seconds: int,
        ip_address: str = None,
    ) -> Execution:
        sandbox = await self.get_sandbox(sandbox_id, user_id)

        if sandbox.status not in (SandboxStatus.READY, SandboxStatus.RUNNING):
            raise ValueError(f"Sandbox {sandbox_id} is not in a runnable state (status={sandbox.status})")

        if datetime.utcnow() > sandbox.expires_at:
            raise ValueError(f"Sandbox {sandbox_id} has expired.")

        sandbox.status = SandboxStatus.RUNNING
        await self.db.flush()

        execution_id = str(uuid.uuid4())
        started_at = datetime.utcnow()

        try:
            result = await self.runtime.exec(
                sandbox.container_id, command, args, timeout_seconds
            )
        except Exception as e:
            logger.error(f"Exec failed in sandbox {sandbox_id}: {e}")
            sandbox.status = SandboxStatus.READY
            SANDBOX_EXECUTION_FAILURES.labels(error_type=type(e).__name__).inc()
            await self.db.commit()
            raise

        finished_at = datetime.utcnow()
        sandbox.status = SandboxStatus.READY

        execution = Execution(
            id=execution_id,
            sandbox_id=sandbox_id,
            command=command,
            args=" ".join(args),
            exit_code=result.exit_code,
            started_at=started_at,
            finished_at=finished_at,
            stdout=result.stdout[:65536],
            stderr=result.stderr[:65536],
            duration_ms=result.duration_ms,
        )
        self.db.add(execution)

        SANDBOX_EXECUTIONS.labels(template=sandbox.template).inc()
        SANDBOX_EXECUTION_DURATION.observe(result.duration_ms / 1000)

        await self._audit(user_id, "EXEC", sandbox_id, details=f"cmd={command}", ip_address=ip_address)
        await self.db.commit()
        return execution

    async def pause_sandbox(self, sandbox_id: str, user_id: str, ip_address: str = None) -> None:
        sandbox = await self.get_sandbox(sandbox_id, user_id)
        if sandbox.status != SandboxStatus.READY:
            raise ValueError(f"Sandbox {sandbox_id} is not READY; cannot pause.")
        await self.runtime.pause(sandbox.container_id)
        sandbox.status = SandboxStatus.PAUSED
        sandbox.paused_at = datetime.utcnow()
        await self._audit(user_id, "PAUSE", sandbox_id, ip_address=ip_address)
        await self.db.commit()

    async def resume_sandbox(self, sandbox_id: str, user_id: str, ip_address: str = None) -> None:
        sandbox = await self.get_sandbox(sandbox_id, user_id)
        if sandbox.status != SandboxStatus.PAUSED:
            raise ValueError(f"Sandbox {sandbox_id} is not PAUSED; cannot resume.")
        await self.runtime.resume(sandbox.container_id)
        sandbox.status = SandboxStatus.READY
        sandbox.paused_at = None
        await self._audit(user_id, "RESUME", sandbox_id, ip_address=ip_address)
        await self.db.commit()

    async def fork_sandbox(self, sandbox_id: str, user_id: str, ttl_seconds: int = 300, ip_address: str = None) -> Sandbox:
        source = await self.get_sandbox(sandbox_id, user_id)
        if source.status not in (SandboxStatus.READY, SandboxStatus.PAUSED):
            raise ValueError(f"Sandbox {sandbox_id} cannot be forked from status {source.status}")

        new_sandbox_id = str(uuid.uuid4())
        now = datetime.utcnow()
        config = SandboxConfig(
            sandbox_id=new_sandbox_id,
            template=source.template,
            cpu_limit=source.cpu_limit,
            memory_mb=source.memory_limit,
            pid_limit=source.pid_limit,
            network_policy=source.network_policy.value,
            ttl_seconds=ttl_seconds,
        )
        new_container_id = await self.runtime.fork(source.container_id, config)

        forked = Sandbox(
            id=new_sandbox_id,
            user_id=user_id,
            status=SandboxStatus.READY,
            template=source.template,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            cpu_limit=source.cpu_limit,
            memory_limit=source.memory_limit,
            pid_limit=source.pid_limit,
            network_policy=source.network_policy,
            container_id=new_container_id,
        )
        self.db.add(forked)
        await self._audit(user_id, "FORK", new_sandbox_id, details=f"forked_from={sandbox_id}", ip_address=ip_address)
        SANDBOXES_CREATED.labels(template=source.template).inc()
        ACTIVE_SANDBOXES.inc()
        await self.db.commit()
        return forked

    async def get_logs(self, sandbox_id: str, user_id: str, tail: int = 100) -> str:
        sandbox = await self.get_sandbox(sandbox_id, user_id)
        if not sandbox.container_id:
            return ""
        return await self.runtime.logs(sandbox.container_id, tail=tail)

    async def _audit(self, user_id: str, action: str, sandbox_id: str = None, details: str = None, ip_address: str = None):
        log = AuditLog(
            user_id=user_id,
            action=action,
            sandbox_id=sandbox_id,
            details=details,
            ip_address=ip_address,
        )
        self.db.add(log)
