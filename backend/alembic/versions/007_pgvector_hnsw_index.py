"""HNSW index on knowledge_documents.embedding_vector.

Revision ID: 007_pgvector_hnsw_index
Revises: 006_jobs_pgvector_retention
"""

from alembic import op

revision = "007_pgvector_hnsw_index"
down_revision = "006_jobs_pgvector_retention"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_knowledge_documents_embedding_hnsw
            ON knowledge_documents
            USING hnsw (embedding_vector vector_cosine_ops)
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP INDEX IF EXISTS ix_knowledge_documents_embedding_hnsw")