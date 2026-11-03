"""photo avatar mesh url

Revision ID: b3e8c1a04f22
Revises: a91c4e2b7d10
Create Date: 2026-10-15 13:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "b3e8c1a04f22"
down_revision: str | None = "a91c4e2b7d10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("body_profiles", sa.Column("avatar_glb_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("body_profiles", "avatar_glb_url")
