"""merge heads add_reference_to_payments_20251106 + ref_pay_251106

Revision ID: c11a6d858826
Revises: add_reference_to_payments_20251106, ref_pay_251106
Create Date: 2025-11-06 10:45:07.929980

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c11a6d858826'
down_revision: Union[str, Sequence[str], None] = ('add_reference_to_payments_20251106', 'ref_pay_251106')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
