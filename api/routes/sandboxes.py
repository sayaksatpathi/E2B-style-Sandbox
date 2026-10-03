import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.rate_limit import limiter
from api.schemas import (
    CreateSandboxRequest, SandboxResponse, SandboxListResponse,
    ExecRequest, ExecResponse, LogsResponse,
)
from database.session import get_db
from sandbox_manager.manager import SandboxManager, QuotaExceededError, SandboxNotFoundError
from runtimes import get_runtime

logger = logging.getLogger(__name__)
router = APIRouter()


def get_manager(db: AsyncSession = Depends(get_db)) -> SandboxManager:
    return SandboxManager(runtime=get_runtime(), db=db)


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


@router.get("", response_model=SandboxListResponse)
@limiter.limit("60/minute")
async def list_sandboxes(
    request: Request,
    user_id: str = Depends(get_current_user),
    manager: SandboxManager = Depends(get_manager),
):
    sandboxes = await manager.list_sandboxes(user_id)
    items = [SandboxResponse.from_orm_sandbox(s) for s in sandboxes]
    return SandboxListResponse(sandboxes=items, total=len(items))


@router.post("", response_model=SandboxResponse, status_code=201)
@limiter.limit("20/minute")
async def create_sandbox(
    body: CreateSandboxRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    manager: SandboxManager = Depends(get_manager),
):
    try:
        sandbox = await manager.create_sandbox(
            user_id=user_id,
            template=body.template,
            ttl_seconds=body.ttl_seconds,
            cpu_limit=body.cpu_limit,
            memory_mb=body.memory_mb,
            network_policy=body.network_policy,
            pid_limit=body.pid_limit,
            ip_address=get_client_ip(request),
        )
        return SandboxResponse.from_orm_sandbox(sandbox)
    except QuotaExceededError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        logger.error(f"create_sandbox error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create sandbox: {str(e)}")


@router.get("/{sandbox_id}", response_model=SandboxResponse)
async def get_sandbox(
    sandbox_id: str,
    user_id: str = Depends(get_current_user),
    manager: SandboxManager = Depends(get_manager),
):
    try:
        sandbox = await manager.get_sandbox(sandbox_id, user_id)
        return SandboxResponse.from_orm_sandbox(sandbox)
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found.")


@router.delete("/{sandbox_id}", status_code=204)
async def delete_sandbox(
    sandbox_id: str,
    request: Request,
    user_id: str = Depends(get_current_user),
    manager: SandboxManager = Depends(get_manager),
):
    try:
        await manager.destroy_sandbox(sandbox_id, user_id, ip_address=get_client_ip(request))
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found.")


@router.post("/{sandbox_id}/exec", response_model=ExecResponse)
@limiter.limit("100/minute")
async def exec_in_sandbox(
    sandbox_id: str,
    body: ExecRequest,
    request: Request,
    user_id: str = Depends(get_current_user),
    manager: SandboxManager = Depends(get_manager),
):
    try:
        execution = await manager.exec_in_sandbox(
            sandbox_id=sandbox_id,
            user_id=user_id,
            command=body.command,
            args=body.args,
            timeout_seconds=body.timeout,
            ip_address=get_client_ip(request),
        )
        return ExecResponse(
            id=execution.id,
            exit_code=execution.exit_code,
            stdout=execution.stdout,
            stderr=execution.stderr,
            duration_ms=execution.duration_ms,
        )
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found.")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        logger.error(f"exec error: {e}")
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")


@router.get("/{sandbox_id}/logs", response_model=LogsResponse)
async def get_logs(
    sandbox_id: str,
    tail: int = 100,
    user_id: str = Depends(get_current_user),
    manager: SandboxManager = Depends(get_manager),
):
    try:
        logs = await manager.get_logs(sandbox_id, user_id, tail=tail)
        return LogsResponse(sandbox_id=sandbox_id, logs=logs)
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found.")


@router.post("/{sandbox_id}/pause", status_code=204)
async def pause_sandbox(
    sandbox_id: str,
    request: Request,
    user_id: str = Depends(get_current_user),
    manager: SandboxManager = Depends(get_manager),
):
    try:
        await manager.pause_sandbox(sandbox_id, user_id, ip_address=get_client_ip(request))
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found.")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{sandbox_id}/resume", status_code=204)
async def resume_sandbox(
    sandbox_id: str,
    request: Request,
    user_id: str = Depends(get_current_user),
    manager: SandboxManager = Depends(get_manager),
):
    try:
        await manager.resume_sandbox(sandbox_id, user_id, ip_address=get_client_ip(request))
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found.")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/{sandbox_id}/fork", response_model=SandboxResponse, status_code=201)
async def fork_sandbox(
    sandbox_id: str,
    request: Request,
    ttl_seconds: int = 300,
    user_id: str = Depends(get_current_user),
    manager: SandboxManager = Depends(get_manager),
):
    try:
        forked = await manager.fork_sandbox(sandbox_id, user_id, ttl_seconds=ttl_seconds, ip_address=get_client_ip(request))
        return SandboxResponse.from_orm_sandbox(forked)
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found.")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
