"""Add unique constraint to ISBN

Revision ID: cbc1a6c1b104
Revises: 92e666bc1e82
Create Date: 2024-01-12 15:18:58.102595

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cbc1a6c1b104'
down_revision: Union[str, None] = '92e666bc1e82'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Assuming your existing table name is 'books'
old_table_name = 'books'
new_table_name = 'books_temp'

def upgrade():
    op.create_table(
        new_table_name,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('title', sa.String),
        sa.Column('isbn', sa.String, unique=True, nullable=True),  # Allow null temporarily
        sa.Column('author', sa.String),
        sa.Column('year', sa.Integer),
        sa.Column('description', sa.String),
        sa.Column('cover', sa.LargeBinary(), nullable=True),
        sa.Column('box_id', sa.Integer, sa.ForeignKey('boxes.id')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('isbn', name='unique_isbn'),
    )

    op.execute(f'INSERT INTO {new_table_name} SELECT * FROM {old_table_name}')
    op.drop_table(old_table_name)
    op.rename_table(new_table_name, old_table_name)


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'books', type_='unique')
    op.drop_constraint('unique_isbn', 'books', type_='unique')
    op.alter_column('books', 'isbn',
               existing_type=sa.VARCHAR(),
               nullable=False)
    # ### end Alembic commands ###
