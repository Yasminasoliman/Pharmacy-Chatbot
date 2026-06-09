from sqlalchemy import text
from .db_engine import engine

def setup_pgvector():

    create_extension_sql = """
    CREATE EXTENSION IF NOT EXISTS vector;
    """

    create_table_sql = """
    CREATE TABLE IF NOT EXISTS medicine_chunks (

        id SERIAL PRIMARY KEY,

        medicine_id INTEGER REFERENCES medicines(id),

        med_name TEXT,

        chunk_index INTEGER,

        chunk_text TEXT,

        embedding VECTOR(384)
    );
    """

    with engine.connect() as connection:

        print("Creating pgvector extension...")

        connection.execute(
            text(create_extension_sql)
        )

        print("Creating medicine_chunks table...")

        connection.execute(
            text(create_table_sql)
        )

        connection.commit()

    print("\npgvector setup completed successfully!")


def create_vector_index():

    create_index_sql = """
    CREATE INDEX IF NOT EXISTS medicine_chunks_embedding_idx
    ON medicine_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
    """

    with engine.connect() as connection:

        print("Creating vector similarity index...")

        connection.execute(
            text(create_index_sql)
        )

        connection.commit()

    print("\nVector index created successfully!")


if __name__ == "__main__":

    setup_pgvector()

    # IMPORTANT:
    # create_vector_index()
    # ONLY AFTER embedding ingestion