from sqlalchemy import text
from db_engine import engine

def setup_pg_trgm():
    """
    Installs pg_trgm extension
    and creates fuzzy search index.
    """

    create_extension_query = """
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
    """

    create_index_query = """
    CREATE INDEX IF NOT EXISTS medicines_name_trgm_idx
    ON medicines
    USING gin (med_name gin_trgm_ops);
    """

    with engine.connect() as connection:

        # Enable extension
        connection.execute(text(create_extension_query))

        # Create index
        connection.execute(text(create_index_query))

        connection.commit()

    print("pg_trgm extension and GIN index created successfully")

if __name__ == "__main__":

    # Run once
    setup_pg_trgm()