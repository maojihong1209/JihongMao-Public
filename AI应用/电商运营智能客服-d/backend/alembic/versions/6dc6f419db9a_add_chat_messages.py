"""add_chat_messages

Revision ID: 6dc6f419db9a
Revises:
Create Date: 2026-05-21 16:04:37.862387
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6dc6f419db9a'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("msg_type", sa.String(20), server_default="text"),
        sa.Column("complaint_level", sa.String(10), nullable=True),
        sa.Column("complaint_type", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        schema="chat_db",
    )
    op.create_index("idx_chat_session", "chat_messages", ["session_id", "created_at"], schema="chat_db")
    op.create_index("idx_chat_user", "chat_messages", ["user_id"], schema="chat_db")


def downgrade() -> None:
    op.drop_table("chat_messages", schema="chat_db")
