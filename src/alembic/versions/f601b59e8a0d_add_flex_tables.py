"""Add Flex tables and tariffs

Revision ID: f601b59e8a0d
Revises: f600b59e8a0d
Create Date: 2024-03-19

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f601b59e8a0d'
down_revision = 'f600b59e8a0d'
branch_labels = None
depends_on = None


def upgrade():
    # Create flex_days table
    op.create_table(
        'flex_days',
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('status', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('date')
    )

    # Create flex_config table
    op.create_table(
        'flex_config',
        sa.Column('key', sa.String(), nullable=False),
        sa.Column('value', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('key')
    )


def downgrade():
    # Drop tables in reverse order
    op.drop_table('flex_config')
    op.drop_table('flex_days')
