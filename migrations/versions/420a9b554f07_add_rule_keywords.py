"""add_rule_keywords

Revision ID: 420a9b554f07
Revises: 405871e7b04a
Create Date: 2026-02-06 12:43:04.259776

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '420a9b554f07'
down_revision = '405871e7b04a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('prototype', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rule_keywords', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('prototype', schema=None) as batch_op:
        batch_op.drop_column('rule_keywords')
