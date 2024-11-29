"""Add tariff_change_date to UsagePoints

Revision ID: add_tariff_change_date
Revises: initial_schema
Create Date: 2024-01-15

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_tariff_change_date'
down_revision = 'initial_schema'
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
