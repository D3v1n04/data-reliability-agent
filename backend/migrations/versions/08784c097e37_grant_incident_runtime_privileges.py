"""grant incident runtime privileges

Revision ID: 08784c097e37
Revises: c983393a2cb8
Create Date: 2026-07-15 23:27:17.378248

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '08784c097e37'
down_revision: Union[str, Sequence[str], None] = 'c983393a2cb8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Grant FastAPI the incident permissions it requires."""
    op.execute(
        "GRANT SELECT, INSERT, UPDATE "
        "ON TABLE public.incidents TO dra_app"
    )


def downgrade() -> None:
    """Remove FastAPI incident permissions."""
    op.execute(
        "REVOKE SELECT, INSERT, UPDATE "
        "ON TABLE public.incidents FROM dra_app"
    )
