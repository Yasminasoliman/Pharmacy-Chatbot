import os
from dotenv import load_dotenv
from model import get_llm

load_dotenv()

DATABASE_URL =  os.getenv("DATABASE_URL")

HF_TOKEN = os.getenv("HF_TOKEN")

LLM = get_llm(
    provider="ollama",
    model_name="llama3.2:3b"
)