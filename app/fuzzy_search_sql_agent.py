from sqlalchemy import text
from setup_database.db_engine import engine


def search_medicine_fuzzy(
    name: str,
    similarity_threshold: float = 0.3,
    limit: int = 5
):
    """
    Fuzzy medicine search using PostgreSQL trigram similarity.

    Args:
        name: medicine name from user input
        similarity_threshold: minimum similarity score
        limit: max number of returned results

    Returns:
        List of matching medicines ordered by similarity
    """

    query = """
    SELECT
        med_name,
        generic_name,
        disease_name,
        final_price,
        prescription_required,
        drug_manufacturer,

        similarity(
            LOWER(med_name),
            LOWER(:medicine_name)
        ) AS similarity_score

    FROM medicines

    WHERE
        LOWER(med_name) ILIKE LOWER(:ilike_pattern)
        OR similarity(
            LOWER(med_name),
            LOWER(:medicine_name)
        ) > :threshold

    ORDER BY similarity_score DESC

    LIMIT :limit;
    """

    with engine.connect() as connection:

        result = connection.execute(
            text(query),
            {
                "medicine_name": name,
                "ilike_pattern": f"%{name}%",
                "threshold": similarity_threshold,
                "limit": limit
            }
        )

        rows = result.fetchall()

    return [dict(row._mapping) for row in rows]


if __name__ == "__main__":

    results = search_medicine_fuzzy("Acne")
    print(results)
    for medicine in results:
        print(medicine)