"""Add scheme timeline / availability columns.

Revision ID: 002_scheme_timeline
Revises: 001_initial
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_scheme_timeline"
down_revision: Union[str, None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("schemes", sa.Column("availability_type", sa.String(length=50), nullable=True))
    op.add_column("schemes", sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True))
    op.add_column("schemes", sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("schemes", "valid_to")
    op.drop_column("schemes", "valid_from")
    op.drop_column("schemes", "availability_type")
