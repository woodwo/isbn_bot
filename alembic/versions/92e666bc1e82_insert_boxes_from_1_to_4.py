"""Insert boxes from 1 to 4

Revision ID: 92e666bc1e82
Revises: 1947bbe6efc9
Create Date: 2024-01-12 12:27:16.535573

"""
from typing import Sequence, Union

from alembic import op
from books.models import Box


# revision identifiers, used by Alembic.
revision: str = '92e666bc1e82'
down_revision: Union[str, None] = '1947bbe6efc9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    op.bulk_insert(
        Box.__table__,
        [
            {'id': 1, 'name_of_the_box': 'Box 1'},
            {'id': 2, 'name_of_the_box': 'Box 2'},
            {'id': 3, 'name_of_the_box': 'Box 3'},
            {'id': 4, 'name_of_the_box': 'Box 4'},
        ]
    )

def downgrade():
    op.execute("DELETE FROM boxes WHERE id BETWEEN 1 AND 4")