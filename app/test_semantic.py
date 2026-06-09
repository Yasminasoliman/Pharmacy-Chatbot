from setup_database.db_engine import execute_query
from embeddings import generate_embeddings, load_embeding_model
import json
from typing_extensions import Optional

def drug_information(
    query: str,
    disease_name: Optional[str],
    med_name: Optional[str],
    generic_name: Optional[str],
    limit: Optional[int] = 3
)-> str:
    """
    Search detailed medical descriptions of medicines or disease or active ingredient(generic_name).

    Args:
        query: str
        med_name: str
        disease_name: str
        generic_name: str
        limit: int


    Returns information that matches the user query meaning:

    Use for explanatory questions.
    """
    if limit == None or limit > 10:
        limit = 3
    embedding_model = load_embeding_model()
    query_embedding = generate_embeddings(query, embedding_model)

    sql_query = """
    SELECT
        mc.med_name,
        mc.chunk_text,

        1 - (
            mc.embedding <=> CAST(:embedding AS vector)
        ) AS similarity_score

    FROM medicine_chunks mc

    JOIN medicines m
    ON mc.medicine_id = m.id

    WHERE 1=1
    """

    params = {
        "embedding": query_embedding,
        "limit": limit
    }

    # Disease filter
    if disease_name:
        sql_query += """
        AND LOWER(m.disease_name) = LOWER(:disease_name)
        """
        params["disease_name"] = disease_name

    # Medicine filter
    if med_name:
        sql_query += """
        AND LOWER(m.med_name) = LOWER(:med_name)
        """
        params["med_name"] = med_name

    # Active ingredient filter
    if generic_name:
        sql_query += """
        AND LOWER(m.generic_name) = LOWER(:generic_name)
        """
        params["generic_name"] = generic_name

    sql_query += """
    ORDER BY mc.embedding <=> CAST(:embedding AS vector)

    LIMIT :limit
    """

    results = execute_query(sql_query, params)

    rows = results.fetchall()

    return json.dumps([dict(row._mapping) for row in rows])


results = drug_information(limit= 4, query= 'precautions for acne medicines', med_name= '', disease_name= 'acne', generic_name= '')

print(results)