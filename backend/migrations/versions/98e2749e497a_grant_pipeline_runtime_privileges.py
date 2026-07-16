"""grant pipeline runtime privileges

Revision ID: 98e2749e497a
Revises: b61d25c710d5
Create Date: 2026-07-16 16:45:40.335401

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '98e2749e497a'
down_revision: Union[str, Sequence[str], None] = 'b61d25c710d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Grant FastAPI the pipeline permissions it requires."""
    op.execute(
        "GRANT SELECT, INSERT "
        "ON TABLE public.pipelines TO dra_app"
    )
    op.execute(
        "GRANT SELECT, INSERT "
        "ON TABLE public.pipeline_runs TO dra_app"
    )


def downgrade() -> None:
    """Remove FastAPI pipeline permissions."""
    op.execute(
        "REVOKE SELECT, INSERT "
        "ON TABLE public.pipeline_runs FROM dra_app"
    )
    op.execute(
        "REVOKE SELECT, INSERT "
        "ON TABLE public.pipelines FROM dra_app"
    )
