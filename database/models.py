from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, ForeignKey, Text, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid

Base = declarative_base()


class SandboxStatus(str, Enum):
    CREATING = "CREATING"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    EXPIRED = "EXPIRED"
    DESTROYING = "DESTROYING"
    DESTROYED = "DESTROYED"
    FAILED = "FAILED"


class NetworkPolicy(str, Enum):
    NONE = "none"
    RESTRICTED = "restricted"
    FULL = "full"


class Sandbox(Base):
    __tablename__ = "sandboxes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(255), nullable=False, index=True)
    status = Column(SAEnum(SandboxStatus), default=SandboxStatus.CREATING, nullable=False)
    template = Column(String(64), nullable=False, default="python")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    cpu_limit = Column(Float, default=1.0)
    memory_limit = Column(Integer, default=512)
    pid_limit = Column(Integer, default=64)
    network_policy = Column(SAEnum(NetworkPolicy), default=NetworkPolicy.RESTRICTED)
    container_id = Column(String(128), nullable=True)
    paused_at = Column(DateTime, nullable=True)

    executions = relationship("Execution", back_populates="sandbox", cascade="all, delete-orphan")


class Execution(Base):
    __tablename__ = "executions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sandbox_id = Column(String(36), ForeignKey("sandboxes.id"), nullable=False, index=True)
    command = Column(String(512), nullable=False)
    args = Column(Text, nullable=True)
    exit_code = Column(Integer, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    stdout = Column(Text, default="")
    stderr = Column(Text, default="")
    duration_ms = Column(Integer, nullable=True)

    sandbox = relationship("Sandbox", back_populates="executions")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(255), nullable=False, index=True)
    action = Column(String(64), nullable=False)
    sandbox_id = Column(String(36), nullable=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    details = Column(Text, nullable=True)
    ip_address = Column(String(45), nullable=True)
