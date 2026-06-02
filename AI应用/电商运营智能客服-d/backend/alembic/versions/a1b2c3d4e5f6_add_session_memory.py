"""add session_memory

Revision ID: a1b2c3d4e5f6
Revises: 8c25142a4e26
Create Date: 2026-06-02
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "9a3b7c1d5e2f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "session_memory",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("summary_text", sa.Text(), server_default=""),
        sa.Column("title", sa.String(50), server_default="新对话"),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
        schema="chat_db",
    )
    op.create_index("ix_session_memory_session_id", "session_memory", ["session_id"], schema="chat_db")


def downgrade() -> None:
    op.drop_table("session_memory", schema="chat_db")
