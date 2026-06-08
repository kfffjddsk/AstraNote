"""sprint-five-container-notes

Revision ID: c7d2a8f1b9e4
Revises: 3b7c9f2d8a1e
Create Date: 2026-06-06 17:54:12.000000

Sprint 5 container rewrite: replace the dual content/encrypted_blob storage
model with a single ``container`` column that holds a self-describing
Container-framed binary blob for every note regardless of encryption state.

Removed columns:
    content          — plaintext was stored directly; now framed in container
    encrypted_blob   — AES-GCM ciphertext; now container holds encrypted bytes
    nonce            — reserved, embedded in blob; container carries its own CRC
    salt             — reserved, embedded in blob; same reason
    payload_location — 'inline'/'filesystem' flag; filesystem fallback removed
    format           — MIME type is now embedded in the container header

Added column:
    container        — BLOB NOT NULL — Container.frame(payload, mime, flags)

Data loss: existing notes are dropped.  The Container format is incompatible
with the previous storage layout; auto-migration is not possible.
[design §5.3]

Refs: [BL B-42, B-74] [REQ R14.3, R14.6] design §3.1, §5.2, §5.3
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "c7d2a8f1b9e4"
down_revision: Union[str, Sequence[str], None] = "3b7c9f2d8a1e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Columns removed in this migration
_REMOVED_COLUMNS = ("content", "encrypted_blob", "nonce", "salt", "payload_location", "format")


def upgrade() -> None:
    """Replace legacy dual-storage columns with a single container blob.

    All existing notes are deleted — the Container binary format is not
    backward-compatible with the old plaintext/ciphertext column layout.
    This data loss is intentional and documented (see migration docstring).
    """
    # Step 1: purge notes that cannot be migrated to the Container format.
    op.execute("DELETE FROM notes")

    # Step 2: recreate the notes table with the new schema.
    # batch_alter_table with recreate="always" works correctly on SQLite,
    # which does not support DROP COLUMN natively before 3.35.
    with op.batch_alter_table("notes", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column("container", sa.LargeBinary(), nullable=False,
                      server_default=sa.text("X''")),   # empty blob; no rows exist
        )
        for col in _REMOVED_COLUMNS:
            batch_op.drop_column(col)

    # Step 3: remove the server_default — application code always supplies the blob.
    with op.batch_alter_table("notes") as batch_op:
        batch_op.alter_column("container", server_default=None)


def downgrade() -> None:
    """Restore the Sprint 2 notes schema.

    Existing notes are deleted — the Container bytes cannot be automatically
    converted back to the legacy column layout.
    """
    op.execute("DELETE FROM notes")

    with op.batch_alter_table("notes", recreate="always") as batch_op:
        batch_op.drop_column("container")
        batch_op.add_column(sa.Column("content", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("format", sa.Text(), nullable=False, server_default="text/plain")
        )
        batch_op.add_column(sa.Column("encrypted_blob", sa.LargeBinary(), nullable=True))
        batch_op.add_column(sa.Column("nonce", sa.LargeBinary(), nullable=True))
        batch_op.add_column(sa.Column("salt", sa.LargeBinary(), nullable=True))
        batch_op.add_column(
            sa.Column("payload_location", sa.Text(), nullable=False, server_default="inline")
        )

    # Clean up server_defaults left by the batch add operations.
    with op.batch_alter_table("notes") as batch_op:
        batch_op.alter_column("format", server_default=None)
        batch_op.alter_column("payload_location", server_default=None)
