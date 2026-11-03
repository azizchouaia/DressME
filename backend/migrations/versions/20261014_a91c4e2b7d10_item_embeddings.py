"""item embeddings for visual search

Revision ID: a91c4e2b7d10
Revises: ece1ca073e36
Create Date: 2026-10-14 23:15:00
"""

from collections.abc import Sequence

from alembic import op


revision: str = "a91c4e2b7d10"
down_revision: str | None = "ece1ca073e36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE item_embeddings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source VARCHAR(32) NOT NULL,
            item_key VARCHAR(64) NOT NULL,
            embedding vector(512) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_item_embeddings_source_key UNIQUE (source, item_key)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX ix_item_embeddings_cosine
            ON item_embeddings USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_item_embeddings_cosine")
    op.execute("DROP TABLE IF EXISTS item_embeddings")
