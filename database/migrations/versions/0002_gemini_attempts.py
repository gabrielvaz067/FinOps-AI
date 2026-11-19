"""Record safe, structured Gemini attempt diagnostics outside public analyses."""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "gemini_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("requested_model", sa.String(length=80), nullable=False),
        sa.Column("attempted_at", sa.DateTime(), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("provider_code", sa.String(length=64), nullable=True),
        sa.Column("provider_reason", sa.String(length=64), nullable=True),
        sa.Column("category", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_id"),
    )


def downgrade():
    op.drop_table("gemini_attempts")
