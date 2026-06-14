"""
ingest_your_data.py
===================
Drop-in script to load your existing DataFrame into the database.

Run this ONCE after cloning the repo.
You can run it from a Jupyter notebook, Google Colab, or the terminal.

─────────────────────────────────────────────────────────────────────────────
OPTION A  ── you already have the DataFrame in memory
─────────────────────────────────────────────────────────────────────────────

    import pandas as pd
    from ingest_your_data import ingest

    df = pd.read_csv("chatbot_ready_medicine_data.csv")
    # OR:  df = your_existing_dataframe

    ingest(df)


─────────────────────────────────────────────────────────────────────────────
OPTION B  ── you have a CSV file
─────────────────────────────────────────────────────────────────────────────

    from ingest_your_data import ingest
    ingest(csv_path="/path/to/chatbot_ready_medicine_data.csv")


─────────────────────────────────────────────────────────────────────────────
OPTION C  ── run from the terminal
─────────────────────────────────────────────────────────────────────────────

    python ingest_your_data.py --csv /path/to/chatbot_ready_medicine_data.csv

    # skip embedding generation (fast reload of just the rows):
    python ingest_your_data.py --csv /path/to/data.csv --skip-embeddings


─────────────────────────────────────────────────────────────────────────────
Expected DataFrame shape
─────────────────────────────────────────────────────────────────────────────

    RangeIndex: 23939 entries, 0 to 23938
    Data columns (total 8):
      disease_name           object
      med_name               object
      generic_name           object
      final_price_clean      float64   ← renamed to final_price on insert
      prescription_required  object
      drug_manufacturer      object
      drug_content           object
      knowledge_text         object
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# make sure app/ is importable
_APP_DIR = Path(__file__).parent / "app"
sys.path.insert(0, str(_APP_DIR))

from app.full_setup import run_setup  # noqa: E402


def ingest(
    df: Optional[pd.DataFrame] = None,
    csv_path: Optional[str] = None,
    skip_embeddings: bool = False,
) -> None:
    """
    Main entry point.

    Parameters
    ----------
    df               : your pandas DataFrame (23939 rows × 8 cols)
    csv_path         : path to a CSV file (alternative to df)
    skip_embeddings  : True = load rows only, skip embedding generation
                       Useful for quick reloads; run with skip_embeddings=False
                       at least once to enable semantic search.
    """
    run_setup(df=df, csv_path=csv_path, skip_embeddings=skip_embeddings)


# ── CLI ──────────────────────────────────────────────────────────────────── #
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Load medicine data into the Pharmacy Chatbot database"
    )
    parser.add_argument(
        "--csv",
        metavar="PATH",
        help="Path to chatbot_ready_medicine_data.csv",
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip embedding generation (fast data reload only)",
    )
    args = parser.parse_args()

    ingest(
        csv_path=args.csv,
        skip_embeddings=args.skip_embeddings,
    )
