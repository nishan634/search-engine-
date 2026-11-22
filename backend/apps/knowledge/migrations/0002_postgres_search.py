"""PostgreSQL-only: pgvector extension, HNSW cosine index on chunks, GIN full-text indexes on chunks and titles.
No-ops on other databases (SQLite is used for the automated tests only)."""
from django.db import migrations


def forwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    ex = schema_editor.execute
    ex("CREATE INDEX IF NOT EXISTS knowledge_chunk_embedding_hnsw ON knowledge_chunk "
       "USING hnsw (embedding vector_cosine_ops)")
    # Expressions mirror SearchVector(<field>, config="english") so the planner can use them.
    ex("CREATE INDEX IF NOT EXISTS knowledge_chunk_fts_gin ON knowledge_chunk USING gin "
       "(to_tsvector('english'::regconfig, COALESCE(text, '')))")
    ex("CREATE INDEX IF NOT EXISTS knowledge_item_title_fts_gin ON knowledge_knowledgeitem USING gin "
       "(to_tsvector('english'::regconfig, COALESCE(title, '')))")


def backwards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute("DROP INDEX IF EXISTS knowledge_chunk_embedding_hnsw")
    schema_editor.execute("DROP INDEX IF EXISTS knowledge_chunk_fts_gin")
    schema_editor.execute("DROP INDEX IF EXISTS knowledge_item_title_fts_gin")


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0001_initial")]
    operations = [migrations.RunPython(forwards, backwards)]
