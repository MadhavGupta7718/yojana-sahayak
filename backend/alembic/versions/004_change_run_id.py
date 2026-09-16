"""Add scraping_run_id to staging_records and data_changes.

Revision ID: 004_change_run_id
Revises: 003_gender_fields
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_change_run_id"
down_revision: Union[str, None] = "003_gender_fields"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "staging_records",
        sa.Column("scraping_run_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_staging_records_scraping_run_id",
        "staging_records",
        "scraping_runs",
        ["scraping_run_id"],
        ["id"],
    )
    op.create_index("ix_staging_records_scraping_run_id", "staging_records", ["scraping_run_id"])

    op.add_column(
        "data_changes",
        sa.Column("scraping_run_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_data_changes_scraping_run_id",
        "data_changes",
        "scraping_runs",
        ["scraping_run_id"],
        ["id"],
    )
    op.create_index("ix_data_changes_scraping_run_id", "data_changes", ["scraping_run_id"])


def downgrade() -> None:
    op.drop_index("ix_data_changes_scraping_run_id", table_name="data_changes")
    op.drop_constraint("fk_data_changes_scraping_run_id", "data_changes", type_="foreignkey")
    op.drop_column("data_changes", "scraping_run_id")

    op.drop_index("ix_staging_records_scraping_run_id", table_name="staging_records")
    op.drop_constraint("fk_staging_records_scraping_run_id", "staging_records", type_="foreignkey")
    op.drop_column("staging_records", "scraping_run_id")
