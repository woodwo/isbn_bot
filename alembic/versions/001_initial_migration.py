# alembic/versions/001_initial_migration.py
from alembic import op
import sqlalchemy as sa

# Make sure to declare the 'revision' variable
revision = '001'
down_revision = None  # This is the first revision

def upgrade():
    op.create_table('boxes',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name_of_the_box', sa.String, nullable=False),
    )

    op.create_table('books',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('title', sa.String, nullable=False),
        sa.Column('isbn', sa.String, nullable=False),
        sa.Column('author', sa.String, nullable=False),
        sa.Column('year', sa.Integer, nullable=False),
        sa.Column('description', sa.String),
        sa.Column('box_id', sa.Integer, sa.ForeignKey('boxes.id', ondelete='CASCADE')),
    )

def downgrade():
    op.drop_table('books')
    op.drop_table('boxes')
