"""add_knowledge_files

Revision ID: 8c25142a4e26
Revises: 6dc6f419db9a
Create Date: 2026-05-21 17:26:49.158586

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c25142a4e26'
down_revision: Union[str, Sequence[str], None] = '6dc6f419db9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_tb",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=False),
        sa.Column("file_size", sa.Integer(), server_default="0"),
        sa.Column("chunk_count", sa.Integer(), server_default="0"),
        sa.Column("status", sa.String(10), server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("operator", sa.String(100), server_default="人工客服"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("file_hash"),
        schema="information_db",
    )


def downgrade() -> None:
    op.drop_table("knowledge_tb", schema="information_db")
