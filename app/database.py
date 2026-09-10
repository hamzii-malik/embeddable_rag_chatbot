import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:1234@localhost:5432/embedd_iq_db")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def init_db():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(text("ALTER TABLE websites ADD COLUMN IF NOT EXISTS error_message TEXT;"))
        conn.execute(text("ALTER TABLE websites ADD COLUMN IF NOT EXISTS current_stage VARCHAR;"))
        conn.execute(text("ALTER TABLE websites ADD COLUMN IF NOT EXISTS pages_scanned INTEGER DEFAULT 0;"))
        conn.execute(text("ALTER TABLE websites ADD COLUMN IF NOT EXISTS chunks_indexed INTEGER DEFAULT 0;"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    # HNSW index for fast approximate cosine similarity search (pgvector).
    # Gemini text-embedding-004 produces 768-dim vectors, so we recreate the
    # index whenever the column dimension changes from the old 1536 default.
    with engine.connect() as conn:
        # Check current vector dimension on the embedding column
        dim_row = conn.execute(text("""
            SELECT atttypmod
            FROM pg_attribute
            JOIN pg_class ON pg_class.oid = pg_attribute.attrelid
            WHERE pg_class.relname = 'document_chunks'
              AND pg_attribute.attname  = 'embedding'
              AND pg_attribute.attnum   > 0;
        """)).fetchone()
        current_dim = dim_row[0] if dim_row else None

        if current_dim != 1536:
            # Remove stale chunks first (wrong-dimension vectors), then retype the column
            conn.execute(text("DELETE FROM document_chunks;"))
            conn.execute(text("DROP INDEX IF EXISTS idx_document_chunks_embedding;"))
            conn.execute(text("ALTER TABLE document_chunks ALTER COLUMN embedding TYPE vector(1536);"))
            conn.commit()

        # Create HNSW index if it doesn't exist yet
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
            ON document_chunks
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64);
        """))
        conn.commit()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()