import os
import re
import json
import requests
import fitz  # PyMuPDF
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from diskcache import Cache

# -------------------------------------------------
# Cache setup
# -------------------------------------------------
CACHE_DIR = "syncra_cache"
cache = Cache(CACHE_DIR)

# -------------------------------------------------
# Weight persistence
# -------------------------------------------------
WEIGHT_FILE = "weights.json"


def load_weights():
    """Load weights from JSON file or return defaults."""
    if os.path.exists(WEIGHT_FILE):
        try:
            with open(WEIGHT_FILE, "r") as f:
                data = json.load(f)
                return data.get("skills", 0.5), data.get("experience", 0.3), data.get("education", 0.2)
        except Exception:
            pass
    return 0.5, 0.3, 0.2


def save_weights(skills, experience, education):
    """Save weights to JSON file."""
    data = {
        "skills": round(skills, 2),
        "experience": round(experience, 2),
        "education": round(education, 2),
    }
    with open(WEIGHT_FILE, "w") as f:
        json.dump(data, f, indent=2)


# -------------------------------------------------
# PDF Text Extraction
# -------------------------------------------------
def extract_text_from_pdf(file):
    """Extract text from a PDF file."""
    text = ""
    try:
        with fitz.open(stream=file.read(), filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
    except Exception:
        text = ""
    return text.strip()


# -------------------------------------------------
# LLM-based Structured Info Extraction (via Ollama)
# -------------------------------------------------
@cache.memoize(expire=3600)
def extract_structured_info(text: str, model: str = "mistral") -> dict:
    """
    Extracts skills, experience, and education using local LLM (Ollama).
    Returns dict with 'skills', 'experience', 'education'.
    """
    prompt = f"""
    Extract only the following details in JSON format:
    {{
        "skills": [list of skills not more than 15 with high probability],
        "experience": "overall relevant experience (years or summary)",
        "education": "education qualifications or degrees mentioned"
    }}

    Text:
    {text}
    """

    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={"model": model, "prompt": prompt, "stream": False},
            timeout=180,
        )
        if response.status_code != 200:
            return {"skills": [], "experience": "", "education": ""}

        raw_output = response.json().get("response", "").strip()
        json_text = re.search(r"\{.*\}", raw_output, re.DOTALL)
        if json_text:
            return json.loads(json_text.group(0))
    except Exception:
        pass

    return {"skills": [], "experience": "", "education": ""}


# -------------------------------------------------
# Embedding-based Weighted Similarity
# -------------------------------------------------
embedder = SentenceTransformer("all-MiniLM-L6-v2")


def weighted_similarity(jd_data: dict, resume_data: dict,
                        w_skills=0.5, w_experience=0.3, w_education=0.2) -> tuple:
    """
    Compute weighted similarity between JD and Resume extracted data.
    Returns (score, reasoning)
    """
    def textify(values):
        if isinstance(values, list):
            return " ".join(values)
        return str(values)

    jd_skills = textify(jd_data.get("skills", []))
    jd_exp = textify(jd_data.get("experience", ""))
    jd_edu = textify(jd_data.get("education", ""))

    res_skills = textify(resume_data.get("skills", []))
    res_exp = textify(resume_data.get("experience", ""))
    res_edu = textify(resume_data.get("education", ""))

    try:
        jd_emb = embedder.encode([jd_skills, jd_exp, jd_edu])
        res_emb = embedder.encode([res_skills, res_exp, res_edu])
    except Exception:
        return 0.0, "Embedding failed"

    skill_sim = cosine_similarity([jd_emb[0]], [res_emb[0]])[0][0]
    exp_sim = cosine_similarity([jd_emb[1]], [res_emb[1]])[0][0]
    edu_sim = cosine_similarity([jd_emb[2]], [res_emb[2]])[0][0]

    final_score = (skill_sim * w_skills + exp_sim * w_experience + edu_sim * w_education) * 10
    final_score = round(min(final_score, 10), 2)

    reasoning = (
        "Strong skill overlap" if skill_sim > 0.8 else
        "Moderate skills match" if skill_sim > 0.5 else
        "Few matching skills"
    )
    reasoning += (
        ", solid experience" if exp_sim > 0.7 else
        ", limited experience" if exp_sim > 0.4 else
        ", weak experience"
    )
    reasoning += (
        ", good education match" if edu_sim > 0.7 else
        ", partial education match" if edu_sim > 0.4 else
        ", poor education match"
    )

    return final_score, reasoning
