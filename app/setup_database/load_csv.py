import pandas as pd
from .db_engine import engine
from pathlib import Path

def load_data():
    current_dir = Path(__file__).parent
    
    project_root = current_dir.parent.parent
    data_file = project_root / "data" / "chatbot_ready_medicine_data.csv"
    df = pd.read_csv(data_file)

    df = df.rename(columns={"final_price_clean": "final_price"})

    df.to_sql(
        "medicines",
        engine,
        if_exists="delete_rows",
        index=False
    )

    print("Dataset loaded successfully")