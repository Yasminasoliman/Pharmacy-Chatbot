from langchain_core.tools import tool
from setup_database.db_engine import execute_query
import json

@tool
def generic_name_lookup(generic_name: str) -> str:
    """
    Retrieve basic information about a generic name (Active ingredient).
    Args:
        generic_name: generic name to search for.

    Returns:
    - medicine name
    - generic name
    - disease name
    - price
    - prescription requirement
    - manufacturer

    Use when the user asks about a active ingredient.
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
    WHERE generic_name ILIKE :generic_name
    LIMIT 10
    """

    results = execute_query(
        query,
        {
            "generic_name": f"%{generic_name}%"
        }
    )

    rows = results.fetchall()
    res = [dict(row._mapping) for row in rows]

    return json.dumps({
        "Number of results": len(res),
        "results": res
    }, default=str)