from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

try:
    from config import DATABASE_URL
except:
    import os
    from dotenv import load_dotenv
    load_dotenv()
    DATABASE_URL = os.getenv('DATABASE_URL')


if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set in the .env file")


engine = create_engine(
    DATABASE_URL
)
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)


def check_connection():
    with engine.connect() as conn:

        result = conn.execute(
            text("SELECT version();")
        )

        print(result.fetchone())
    return True
   

def execute_query(query, params=None):

    with engine.begin() as connection:

        result = connection.execute(
            text(query),
            params
        )

        return result
    


if __name__ == "__main__":
    check_connection()