from sqlalchemy import text
from .db_engine import engine

def create_medicine_table():
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS medicines (

        id SERIAL PRIMARY KEY,

        disease_name TEXT,

        med_name TEXT,

        final_price TEXT,

        prescription_required TEXT,

        drug_manufacturer TEXT,

        drug_content TEXT,

        generic_name TEXT,

        knowledge_text TEXT
    );
    """

    with engine.connect() as connection:

        connection.execute(text(create_table_sql))

        connection.commit()

    print("medicines table created successfully")