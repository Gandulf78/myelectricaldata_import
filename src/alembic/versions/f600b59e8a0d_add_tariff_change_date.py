"""Add tariff_change_date to UsagePoints

Revision ID: f600b59e8a0d
Revises: e990284249e4
Create Date: 2024-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f600b59e8a0d'
down_revision = 'e990284249e4'
branch_labels = None
depends_on = None


def upgrade():
    # Add tariff_change_date column to usage_points table
    op.add_column('usage_points',
        sa.Column('tariff_change_date', sa.DateTime, nullable=True)
    )


def downgrade():
    # Remove tariff_change_date column from usage_points table
    op.drop_column('usage_points', 'tariff_change_date')
