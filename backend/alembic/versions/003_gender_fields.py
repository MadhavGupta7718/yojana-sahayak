"""Add user gender and scheme target_gender.

Revision ID: 003_gender_fields
Revises: 002_scheme_timeline
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_gender_fields"
down_revision: Union[str, None] = "002_scheme_timeline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("gender", sa.String(length=50), nullable=True))
    op.add_column(
        "schemes",
        sa.Column("target_gender", sa.String(length=50), nullable=True, server_default="any"),
    )


def downgrade() -> None:
    op.drop_column("schemes", "target_gender")
    op.drop_column("users", "gender")
