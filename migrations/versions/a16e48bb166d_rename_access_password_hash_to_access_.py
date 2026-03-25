"""rename access_password_hash to access_password

Revision ID: a16e48bb166d
Revises: e7f63a8cceee
Create Date: 2026-02-05 23:45:39.655384

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a16e48bb166d'
down_revision = 'e7f63a8cceee'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('prototype', schema=None) as batch_op:
        batch_op.alter_column('access_password_hash', new_column_name='access_password')

def downgrade():
    with op.batch_alter_table('prototype', schema=None) as batch_op:
        batch_op.alter_column('access_password', new_column_name='access_password_hash')
