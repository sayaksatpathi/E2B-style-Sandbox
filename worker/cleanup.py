"""
Background cleanup worker.

Runs as a separate process.  Periodically:
  1. Finds sandboxes whose expires_at < now and status is not already terminal.
  2. Destroys their containers.
  3. Marks them EXPIRED / DESTROYED.
"""

import asyncio
import logging
import os
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.session import AsyncSessionLocal, init_db
from database.models import Sandbox, SandboxStatus
from runtimes import get_runtime
from observability.metrics import SANDBOXES_DESTROYED, ACTIVE_SANDBOXES, SANDBOX_EXPIRED

logger = logging.getLogger(__name__)

CLEANUP_INTERVAL = int(os.getenv("CLEANUP_INTERVAL_SECONDS", "30"))

TERMINAL_STATUSES = {SandboxStatus.DESTROYED, SandboxStatus.FAILED, SandboxStatus.EXPIRED}


async def cleanup_expired_sandboxes():
    runtime = get_runtime()
    async with AsyncSessionLocal() as db:
        try:
            now = datetime.utcnow()
            result = await db.execute(
                select(Sandbox).where(
                    Sandbox.expires_at < now,
                    Sandbox.status.notin_(TERMINAL_STATUSES),
                    Sandbox.status != SandboxStatus.DESTROYING,
                )
            )
            expired = result.scalars().all()
            if not expired:
                return

            logger.info(f"Cleaning up {len(expired)} expired sandboxes")

            for sandbox in expired:
                sandbox.status = SandboxStatus.DESTROYING
            await db.flush()

            for sandbox in expired:
                if sandbox.container_id:
                    try:
                        await runtime.destroy(sandbox.container_id)
                    except Exception as e:
                        logger.warning(f"Error destroying container for {sandbox.id}: {e}")

                sandbox.status = SandboxStatus.DESTROYED
                SANDBOXES_DESTROYED.labels(reason="expired").inc()
                SANDBOX_EXPIRED.inc()
                try:
                    ACTIVE_SANDBOXES.dec()
                except Exception:
                    pass

            await db.commit()
            logger.info(f"Cleaned up {len(expired)} sandboxes.")
        except Exception as e:
            logger.error(f"Cleanup error: {e}", exc_info=True)
            await db.rollback()


async def run_worker():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("Starting cleanup worker")
    await init_db()
    while True:
        try:
            await cleanup_expired_sandboxes()
        except Exception as e:
            logger.error(f"Worker loop error: {e}", exc_info=True)
        await asyncio.sleep(CLEANUP_INTERVAL)


if __name__ == "__main__":
    asyncio.run(run_worker())
