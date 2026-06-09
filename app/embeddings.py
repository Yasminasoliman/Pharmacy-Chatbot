from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from config import HF_TOKEN


def load_embeding_model():
    import torch

    device = "cuda" if torch.cuda.is_available() else "cpu"

    embedding_model = SentenceTransformer(
        "BAAI/bge-small-en-v1.5",
        device=device,
        token=HF_TOKEN
    )

    print("Embedding model loaded")
    return embedding_model

def generate_embeddings(texts, embedding_model):

    embeddings = embedding_model.encode(
        texts,

        batch_size=128,

        show_progress_bar=False,

        normalize_embeddings=True
    )

    return embeddings.tolist()