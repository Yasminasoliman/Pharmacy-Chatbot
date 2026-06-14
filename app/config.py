import os
from dotenv import load_dotenv
from model import get_llm

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
HF_TOKEN     = os.getenv("HF_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Text LLM — for chat, search, reasoning
LLM = get_llm(
    provider="groq",
    model_name="llama-3.3-70b-versatile",
    api_key=GROQ_API_KEY,
)

# Vision LLM — for OCR / prescription images
VISION_LLM = get_llm(
    provider="groq",
    model_name="meta-llama/llama-4-scout-17b-16e-instruct",
    api_key=GROQ_API_KEY,
)