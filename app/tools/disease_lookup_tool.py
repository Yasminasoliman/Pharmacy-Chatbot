from langchain_core.tools import tool
from setup_database.db_engine import execute_query
import json

@tool
def disease_lookup(disease_name: str) -> str:
    """
    Retrieve basic information about a disease.
    Args:
        disease_name: disease name to search for.

    Returns:
    - medicine name
    - generic name
    - disease name
    - price
    - prescription requirement
    - manufacturer

    Use when the user asks about a specific disease.
    """

    query = """
    SELECT
        med_name,
        generic_name,
        disease_name,
        final_price,
        prescription_required,
        drug_manufacturer
    FROM medicines
    WHERE disease_name ILIKE :disease_name
    LIMIT 10
    """

    results = execute_query(
        query,
        {
            "disease_name": f"%{disease_name}%"
        }
    )

    rows = results.fetchall()
    res = [dict(row._mapping) for row in rows]

    return json.dumps({
        "Number of results": len(res),
        "results": res
    }, default=str)