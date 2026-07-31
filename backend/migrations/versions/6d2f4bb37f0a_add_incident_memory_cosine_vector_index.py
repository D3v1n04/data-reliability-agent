"""add incident memory cosine vector index

Revision ID: 6d2f4bb37f0a
Revises: 0d2a36f0f406
Create Date: 2026-07-31

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "6d2f4bb37f0a"
down_revision: Union[str, Sequence[str], None] = "0d2a36f0f406"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


INDEX_NAME = "ix_incident_memories_embedding_cosine"


def upgrade() -> None:
    """Create the distributed cosine ANN index used by memory retrieval."""
    op.execute(
        f"CREATE VECTOR INDEX {INDEX_NAME} "
        "ON incident_memories (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    """Remove the cosine vector index without deleting incident memory."""
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME}")
