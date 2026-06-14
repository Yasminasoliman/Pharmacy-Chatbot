"""
load_embeddings_from_colab.py
Loads the Colab-generated embeddings CSV into PostgreSQL.
Run after downloading medicine_chunks_with_embeddings.csv from Colab.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent / "app"))
from app.setup_database.db_engine import engine


def load(csv_path: str):
    print(f"Reading {csv_path}...")
    df = pd.read_csv(csv_path)
    print(f"  {len(df):,} rows loaded")

    # 1. enable pgvector
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()

    # 2. create medicine_chunks table
    create_sql = """
    CREATE TABLE IF NOT EXISTS medicine_chunks (
        id           SERIAL PRIMARY KEY,
        medicine_id  INTEGER REFERENCES medicines(id),
        chunk_text   TEXT,
        embedding    vector(384)
    );
    """
    with engine.connect() as conn:
        conn.execute(text(create_sql))
        conn.commit()
    print("  Table medicine_chunks ready")

    # 3. insert in batches
    batch_size = 500
    total = len(df)
    inserted = 0

    with engine.connect() as conn:
        for start in range(0, total, batch_size):
            batch = df.iloc[start : start + batch_size]
            rows = []
            for _, row in batch.iterrows():
                vec = row['embedding']
                # handle both JSON string and plain string formats
                if isinstance(vec, str):
                    vec_list = json.loads(vec)
                else:
                    vec_list = list(vec)
                rows.append({
                    "medicine_id": int(row['medicine_id']),
                    "chunk_text":  row['chunk_text'],
                    "embedding":   str(vec_list),
                })

            conn.execute(
                text("""
                    INSERT INTO medicine_chunks (medicine_id, chunk_text, embedding)
                    VALUES (:medicine_id, :chunk_text, CAST(:embedding AS vector))
                """),
                rows,
            )
            conn.commit()
            inserted += len(batch)
            pct = inserted / total * 100
            print(f"  {inserted:,}/{total:,} ({pct:.1f}%) inserted", end="\r")

    print(f"\n✓ {inserted:,} embedding rows loaded")

    # 4. build vector index
    print("Building vector index (ivfflat)...")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_medicine_chunks_embedding
            ON medicine_chunks
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
        """))
        conn.commit()
    print("✓ Index built")
    print("\n✅ All done! Semantic search is ready.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True, help="Path to medicine_chunks_with_embeddings.csv")
    args = parser.parse_args()
    load(args.csv)