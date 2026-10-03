from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator


class CreateSandboxRequest(BaseModel):
    template: str = Field(default="python", pattern="^(python|node|bash|go|ruby)$")
    ttl_seconds: int = Field(default=300, ge=30, le=3600)
    cpu_limit: float = Field(default=1.0, ge=0.1, le=4.0)
    memory_mb: int = Field(default=512, ge=64, le=4096)
    network_policy: str = Field(default="restricted", pattern="^(none|restricted|full)$")
    pid_limit: int = Field(default=64, ge=8, le=256)


class SandboxResponse(BaseModel):
    id: str
    user_id: str
    status: str
    template: str
    created_at: datetime
    expires_at: datetime
    cpu_limit: float
    memory_mb: int
    network_policy: str

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_sandbox(cls, s):
        return cls(
            id=s.id,
            user_id=s.user_id,
            status=s.status.value if hasattr(s.status, 'value') else s.status,
            template=s.template,
            created_at=s.created_at,
            expires_at=s.expires_at,
            cpu_limit=s.cpu_limit,
            memory_mb=s.memory_limit,
            network_policy=s.network_policy.value if hasattr(s.network_policy, 'value') else s.network_policy,
        )


class ExecRequest(BaseModel):
    command: str = Field(..., min_length=1, max_length=256)
    args: List[str] = Field(default_factory=list)
    timeout: int = Field(default=30, ge=1, le=120)

    @field_validator("command")
    @classmethod
    def no_shell_injection(cls, v):
        dangerous = [";", "&&", "||", "`", "$(", "|", ">", "<", "\n", "\r"]
        for d in dangerous:
            if d in v:
                raise ValueError(f"Command contains disallowed character sequence: {d!r}")
        return v


class ExecResponse(BaseModel):
    id: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool = False


class LogsResponse(BaseModel):
    sandbox_id: str
    logs: str


class TokenRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class SandboxListResponse(BaseModel):
    sandboxes: List[SandboxResponse]
    total: int


class HealthResponse(BaseModel):
    status: str
    database: str
    runtime: str
    version: str = "1.0.0"
