"""grant incident memory runtime privileges

Revision ID: 0d2a36f0f406
Revises: c25f84c7af1c
Create Date: 2026-07-27 15:56:39.391151

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0d2a36f0f406'
down_revision: Union[str, Sequence[str], None] = 'c25f84c7af1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Grant FastAPI the incident-memory permissions it requires."""
    op.execute(
        "GRANT SELECT, INSERT "
        "ON TABLE public.incident_memories TO dra_app"
    )
    op.execute(
        "GRANT SELECT, INSERT "
        "ON TABLE public.incident_diagnoses TO dra_app"
    )


def downgrade() -> None:
    """Remove FastAPI incident-memory permissions."""
    op.execute(
        "REVOKE SELECT, INSERT "
        "ON TABLE public.incident_diagnoses FROM dra_app"
    )
    op.execute(
        "REVOKE SELECT, INSERT "
        "ON TABLE public.incident_memories FROM dra_app"
    )
