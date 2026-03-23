"""Initial schema — executions table.

Revision ID: 001
Revises: None
Create Date: 2026-03-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "executions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("execution_id", sa.String(50), nullable=False),
        sa.Column("workflow_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("duration_ms", sa.Integer(), server_default="0"),
        sa.Column("extracted_variables", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_executions_execution_id", "executions", ["execution_id"], unique=True)
    op.create_index("ix_executions_workflow_name", "executions", ["workflow_name"])


def downgrade() -> None:
    op.drop_index("ix_executions_workflow_name", table_name="executions")
    op.drop_index("ix_executions_execution_id", table_name="executions")
    op.drop_table("executions")
