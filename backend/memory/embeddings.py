import threading
from typing import List, Dict, Any

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384
EMBEDDING_VERSION = "1.0.0"

_model_lock = threading.Lock()
_model_instance = None

def get_embedding_model():
    """Lazy-loads and returns the SentenceTransformer model in a thread-safe manner."""
    global _model_instance
    with _model_lock:
        if _model_instance is None:
            # We import here to avoid loading torch/transformers unnecessarily on startup
            from sentence_transformers import SentenceTransformer
            # Disable symlinks warnings on Windows if any
            _model_instance = SentenceTransformer(EMBEDDING_MODEL)
        return _model_instance

def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """Generates embedding vectors for a list of text strings."""
    if not texts:
        return []
    model = get_embedding_model()
    embeddings = model.encode(texts, show_progress_bar=False)
    # Convert numpy float32 ndarray to Python float lists
    return [vec.tolist() for vec in embeddings]

def generate_embedding(text: str) -> List[float]:
    """Generates an embedding vector for a single text string."""
    return generate_embeddings([text])[0]

def get_model_metadata() -> Dict[str, Any]:
    """Returns the metadata of the currently active embedding model."""
    return {
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimension": EMBEDDING_DIMENSION,
        "embedding_version": EMBEDDING_VERSION
    }
