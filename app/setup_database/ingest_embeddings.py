from sqlalchemy import text
from chunking import chunk_text
from embeddings import generate_embeddings, load_embeding_model
from tqdm import tqdm
from .db_engine import engine


BATCH_SIZE = 128


def ingest_medicine_embeddings():

    embedding_model = load_embeding_model()

    select_query = """
    SELECT
        id,
        med_name,
        knowledge_text
    FROM medicines
    """

    insert_query = """
    INSERT INTO medicine_chunks (
        medicine_id,
        med_name,
        chunk_index,
        chunk_text,
        embedding
    )
    VALUES (
        :medicine_id,
        :med_name,
        :chunk_index,
        :chunk_text,
        :embedding
    )
    """

    with engine.begin() as connection:

        print("Fetching medicines...")

        medicines = connection.execute(
            text(select_query)
        ).fetchall()

        print(f"Found {len(medicines)} medicines")

        embedding_batch = []

        total_chunks = 0

        for medicine in tqdm(
            medicines,
            desc="Processing medicines"
        ):

            if not medicine.knowledge_text:
                continue

            chunks = chunk_text(
                medicine.knowledge_text
            )

            total_chunks += len(chunks)

            for index, chunk in enumerate(chunks):

                embedding_batch.append({
                    "medicine_id": medicine.id,
                    "med_name": medicine.med_name,
                    "chunk_index": index,
                    "chunk_text": chunk
                })

                # Process batch
                if len(embedding_batch) >= BATCH_SIZE:

                    process_batch(
                        connection,
                        embedding_batch,
                        insert_query,
                        embedding_model
                    )

                    embedding_batch.clear()

        # Remaining chunks
        if embedding_batch:

            process_batch(
                connection,
                embedding_batch,
                insert_query,
                embedding_model
            )

        print(f"\nTotal chunks embedded: {total_chunks}")

    print("\nEmbedding ingestion completed successfully")



def process_batch(
    connection,
    batch,
    insert_query,
    embedding_model
):

    texts = [
        item["chunk_text"]
        for item in batch
    ]

    embeddings = generate_embeddings(
        texts,
        embedding_model
    )

    rows = []

    for item, embedding in zip(batch, embeddings):

        rows.append({
            "medicine_id": item["medicine_id"],
            "med_name": item["med_name"],
            "chunk_index": item["chunk_index"],
            "chunk_text": item["chunk_text"],
            "embedding": embedding
        })

    connection.execute(
        text(insert_query),
        rows
    )


if __name__ == "__main__":

    import torch

    print(torch.cuda.is_available())
    ingest_medicine_embeddings()