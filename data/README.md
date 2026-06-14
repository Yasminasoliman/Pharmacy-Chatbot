# data/

Place your CSV file here:

    data/chatbot_ready_medicine_data.csv

Expected columns (8):
| Column                | Type    | Notes                              |
|-----------------------|---------|------------------------------------|
| disease_name          | str     | e.g. "ADHD", "Diabetes"            |
| med_name              | str     | Brand name e.g. "Panadol 500mg"    |
| generic_name          | str     | e.g. "Paracetamol 500 mg"          |
| final_price_clean     | float64 | e.g. 335.68                        |
| prescription_required | str     | "Rx required" or "OTC"             |
| drug_manufacturer     | str     | e.g. "Cipla Ltd"                   |
| drug_content          | str     | Full drug description text         |
| knowledge_text        | str     | Structured knowledge for RAG       |

23,939 rows expected.

Alternatively, pass the DataFrame directly:

    from ingest_your_data import ingest
    ingest(df=your_dataframe)
