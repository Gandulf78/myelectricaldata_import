"""Add tariff history

Revision ID: f602b59e8a0d
Revises: f601b59e8a0d
Create Date: 2024-03-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f602b59e8a0d'
down_revision = 'f601b59e8a0d'
branch_labels = None
depends_on = None


def upgrade():
    # Add previous_tariff column to usage_points table
    op.add_column('usage_points', sa.Column('previous_tariff', sa.String(), nullable=True))


def downgrade():
    # Drop previous_tariff column from usage_points table
    op.drop_column('usage_points', 'previous_tariff')
