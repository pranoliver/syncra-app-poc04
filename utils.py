import requests
import numpy as np
import hashlib
import json
from sklearn.metrics.pairwise import cosine_similarity
from PyPDF2 import PdfReader
import diskcache as dc
import os

# ---------------------------------------------------------
# CACHE INITIALIZATION
# ---------------------------------------------------------
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
os.makedirs(CACHE_DIR, exist_ok=True)
cache = dc.Cache(CACHE_DIR)

OLLAMA_API = "http://localhost:11434/api"


# ---------------------------------------------------------
# FILE HASH
# ---------------------------------------------------------
def file_hash(file):
    file.seek(0)
    content = file.read()
    file.seek(0)
    return hashlib.sha256(content).hexdigest()


# ---------------------------------------------------------
# PDF TEXT EXTRACTION
# ---------------------------------------------------------
@cache.memoize()
def extract_text_from_pdf_cached(content: bytes):
    from io import BytesIO

    reader = PdfReader(BytesIO(content))
    text = ""
    for page in reader.pages:
        text += page.extract_text() or ""
    return text.strip()


def extract_text_from_pdf(file):
    return extract_text_from_pdf_cached(file.read())


# ---------------------------------------------------------
# LIST LOCAL MODELS
# ---------------------------------------------------------
def list_ollama_models():
    try:
        resp = requests.get(f"{OLLAMA_API}/tags")
        if resp.status_code == 200:
            data = resp.json()
            return [m["name"] for m in data["models"]]
    except Exception:
        pass
    return ["mistral"]


# ---------------------------------------------------------
# EMBEDDINGS FROM OLLAMA
# ---------------------------------------------------------
@cache.memoize()
def get_embedding_ollama(text, model="mistral"):
    if not text.strip():
        return np.zeros((1, 384))
    payload = {"model": model, "prompt": text}
    try:
        resp = requests.post(f"{OLLAMA_API}/embeddings", json=payload)
        if resp.status_code == 200:
            return np.array(resp.json()["embedding"]).reshape(1, -1)
    except Exception:
        pass
    return np.zeros((1, 384))


# ---------------------------------------------------------
# MINI-LM EMBEDDINGS
# ---------------------------------------------------------
@cache.memoize()
def get_embedding_minilm(text):
    try:
        from sentence_transformers import SentenceTransformer

        if not text.strip():
            return np.zeros((1, 384))
        model = SentenceTransformer("all-MiniLM-L6-v2")
        emb = model.encode([text])
        return np.array(emb)
    except Exception as e:
        print(f"MiniLM error: {e}")
        return np.zeros((1, 384))


# ---------------------------------------------------------
# SIMILARITY
# ---------------------------------------------------------
def compute_similarity(job_emb, resume_emb):
    if job_emb.shape[1] == 0 or resume_emb.shape[1] == 0:
        return 0
    similarity = cosine_similarity(job_emb, resume_emb)[0][0]
    return round(similarity * 10, 2)


# ---------------------------------------------------------
# REASONING
# ---------------------------------------------------------
@cache.memoize()
def generate_reasoning(jd_text, resume_text, model="mistral"):
    prompt = f"""
    Compare the following job description and resume.
    Provide reasoning why the candidate fits or does not fit the role.

    JOB DESCRIPTION:
    {jd_text[:3000]}

    RESUME:
    {resume_text[:3000]}

    Respond clearly in 3-4 sentences.
    """
    try:
        payload = {"model": model, "prompt": prompt, "stream": False}
        resp = requests.post(f"{OLLAMA_API}/generate", json=payload)
        if resp.status_code == 200:
            data = json.loads(resp.text)
            return data.get("response", "").strip()
    except Exception:
        return "Unable to generate reasoning."
    return "No response."


# ---------------------------------------------------------
# CACHE MANAGEMENT
# ---------------------------------------------------------
def clear_all_cache():
    cache.clear()
    return "All cached data cleared successfully!"
