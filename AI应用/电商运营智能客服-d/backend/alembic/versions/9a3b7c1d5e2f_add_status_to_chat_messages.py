"""add status column to chat_messages

Revision ID: 9a3b7c1d5e2f
Revises: 8c25142a4e26
Create Date: 2026-05-21 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9a3b7c1d5e2f'
down_revision: Union[str, Sequence[str], None] = '8c25142a4e26'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chat_messages",
        sa.Column("status", sa.String(10), server_default="active"),
        schema="chat_db",
    )
    op.create_index(
        "ix_chat_messages_status",
        "chat_messages",
        ["status"],
        schema="chat_db",
    )


def downgrade() -> None:
    op.drop_index("ix_chat_messages_status", table_name="chat_messages", schema="chat_db")
    op.drop_column("chat_messages", "status", schema="chat_db")
