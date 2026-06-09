from setup_database.db_engine import engine, check_connection
from setup_database.setup_medicines_table import create_medicine_table
from setup_database.load_csv import load_data
from setup_database.setup_pgvector import setup_pgvector, create_vector_index
from setup_database.ingest_embeddings import ingest_medicine_embeddings

if __name__ == "__main__":
    if(check_connection):
        create_medicine_table()
        load_data()
        setup_pgvector()
        ingest_medicine_embeddings()
        create_vector_index()