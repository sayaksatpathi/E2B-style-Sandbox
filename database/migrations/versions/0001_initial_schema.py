"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sandboxes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(256), nullable=False, index=True),
        sa.Column(
            "status",
            sa.Enum(
                "CREATING", "READY", "RUNNING", "PAUSED",
                "EXPIRED", "DESTROYING", "DESTROYED", "FAILED",
                name="sandboxstatus",
            ),
            nullable=False,
        ),
        sa.Column("template", sa.String(64), nullable=False),
        sa.Column("container_id", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=False, index=True),
        sa.Column("paused_at", sa.DateTime, nullable=True),
        sa.Column("cpu_limit", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("memory_limit", sa.Integer, nullable=False, server_default="512"),
        sa.Column("pid_limit", sa.Integer, nullable=False, server_default="64"),
        sa.Column(
            "network_policy",
            sa.Enum("none", "restricted", "full", name="networkpolicy"),
            nullable=False,
            server_default="restricted",
        ),
    )

    op.create_table(
        "executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sandbox_id", sa.String(36), sa.ForeignKey("sandboxes.id"), nullable=False, index=True),
        sa.Column("command", sa.String(256), nullable=False),
        sa.Column("args", sa.Text, nullable=True),
        sa.Column("exit_code", sa.Integer, nullable=True),
        sa.Column("started_at", sa.DateTime, nullable=False),
        sa.Column("finished_at", sa.DateTime, nullable=True),
        sa.Column("stdout", sa.Text, nullable=True),
        sa.Column("stderr", sa.Text, nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(256), nullable=False, index=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("sandbox_id", sa.String(36), nullable=True),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("executions")
    op.drop_table("sandboxes")
    op.execute("DROP TYPE IF EXISTS sandboxstatus")
    op.execute("DROP TYPE IF EXISTS networkpolicy")
