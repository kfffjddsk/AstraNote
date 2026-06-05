"""Initial server_notes table.

Revision ID: 0001
Revises:
Create Date: 2026-06-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the server_notes table and its indexes."""
    op.create_table(
        "server_notes",
        sa.Column("note_id", sa.Text(), nullable=False),
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("is_encrypted", sa.Boolean(), nullable=False),
        sa.Column("encrypted_blob", sa.LargeBinary(), nullable=True),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("modified_at", sa.Text(), nullable=False),
        sa.Column("server_synced_at", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("note_id", "account_id"),
    )
    op.create_index("ix_server_notes_account", "server_notes", ["account_id"])
    op.create_index(
        "ix_server_notes_account_modified",
        "server_notes",
        ["account_id", "modified_at"],
    )


def downgrade() -> None:
    """Drop the server_notes table."""
    op.drop_index("ix_server_notes_account_modified", table_name="server_notes")
    op.drop_index("ix_server_notes_account", table_name="server_notes")
    op.drop_table("server_notes")
