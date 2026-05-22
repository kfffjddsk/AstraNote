"""sprint-two-accounts

Revision ID: 3b7c9f2d8a1e
Revises: e2f2634ce4f7
Create Date: 2026-05-21 00:00:00.000000

Sprint 2 migration: add the ``accounts`` table for the optional local account
layer.  The ``notes`` table already has ``account_id`` (nullable FK, added in
Sprint 0 baseline) and ``synced_at`` (nullable timestamp).  This migration
only adds the new ``accounts`` table.

Refs: [BL B-45, B-96] [REQ R13.1-R13.12, R14.10]
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "3b7c9f2d8a1e"
down_revision: Union[str, Sequence[str], None] = "e2f2634ce4f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the accounts table.  [BL B-96] [REQ R14.10]"""
    op.create_table(
        "accounts",
        sa.Column("account_id", sa.Text(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.Text(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("account_id"),
        sa.UniqueConstraint("username", name="uq_accounts_username"),
    )


def downgrade() -> None:
    """Drop the accounts table."""
    op.drop_table("accounts")
