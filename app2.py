import os
import streamlit as st
from utils2 import (
    extract_text_from_pdf,
    extract_structured_info,
    weighted_similarity,
    load_weights,
    save_weights,
)
import pandas as pd
from diskcache import Cache

# -------------------------------------------------
# Page Config
# -------------------------------------------------
st.set_page_config(page_title="Syncra - Resume Matcher", layout="wide")

# -------------------------------------------------
# Logo + Header
# -------------------------------------------------
st.markdown(
    """
    <style>
    .syncra-header {
        display: flex;
        align-items: center;
        justify-content: left;
        gap: 1rem;
    }
    .syncra-header img {
        height: 64px;
    }
    .syncra-title {
        font-size: 2.2rem;
        font-family: 'Outfit', sans-serif;
        font-weight: 600;
    }
    .syncra-caption {
        font-size: 1.1rem;
        font-family: 'Outfit', sans-serif;
        color: #8A8A8A;
        margin-top: -10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

col_logo, col_title = st.columns([1, 4])
with col_logo:
    st.image("syncra_logo_01.png", width='content')
with col_title:
    st.markdown("<div class='syncra-title'>Resume Match Results</div>", unsafe_allow_html=True)
    st.markdown("<div class='syncra-caption'>Elegant, Explainable, and Entirely Local</div>", unsafe_allow_html=True)

st.write("---")

# -------------------------------------------------
# Sidebar - Input + Model + Weights
# -------------------------------------------------
st.sidebar.header("🧩 Input Files")

jd_file = st.sidebar.file_uploader("📄 Job Description (PDF)", type=["pdf"])
resumes = st.sidebar.file_uploader("📑 Candidate Resumes (PDFs)", type=["pdf"], accept_multiple_files=True)

# Model selection
st.sidebar.markdown("### 🧠 Select Local LLM")
selected_model = st.sidebar.selectbox("Choose Model (installed in Ollama)", ["deepseek-r1", "mistral:latest", "phi3", "qwen2"], index=0)

# ---------------------------------------------
# WEIGHT CONFIGURATION (AUTO-SAVE)
# ---------------------------------------------
st.sidebar.markdown("### ⚖️ Weighted Scoring")

default_skills, default_experience, default_education = load_weights()

w_skills = st.sidebar.slider("Skills Weight", 0.0, 1.0, default_skills, 0.05, key="skills_weight")
w_experience = st.sidebar.slider("Experience Weight", 0.0, 1.0, default_experience, 0.05, key="exp_weight")
w_education = st.sidebar.slider("Education Weight", 0.0, 1.0, default_education, 0.05, key="edu_weight")

# Normalize
total = w_skills + w_experience + w_education
if total == 0:
    total = 1.0
w_skills, w_experience, w_education = (
    w_skills / total,
    w_experience / total,
    w_education / total,
)

# Auto-save weights on change
if (
    w_skills != default_skills
    or w_experience != default_experience
    or w_education != default_education
):
    save_weights(w_skills, w_experience, w_education)
    st.sidebar.info("💾 Weights auto-saved")

st.sidebar.caption(
    f"Normalized Weights → 🧩 Skills: {w_skills:.2f} | 🧠 Exp: {w_experience:.2f} | 🎓 Edu: {w_education:.2f}"
)

if st.sidebar.button("♻️ Reset to Default"):
    if os.path.exists("weights.json"):
        os.remove("weights.json")
        st.sidebar.warning("Weights reset to default. Please reload the app.")

# -------------------------------------------------
# Cache summary
# -------------------------------------------------
cache = Cache("syncra_cache")
cache_size = sum(os.path.getsize(os.path.join(root, file)) for root, _, files in os.walk("syncra_cache") for file in files) / (1024 * 1024)
st.sidebar.markdown(f"🗂️ **Cache Summary:** {len(cache)} items | {cache_size:.1f} MB")

if st.sidebar.button("🧹 Clear Cache"):
    cache.clear()
    st.sidebar.success("Cache cleared successfully!")

# -------------------------------------------------
# Main Area - Analysis
# -------------------------------------------------
st.write("## 🧠 Resume Analysis Dashboard")

if jd_file and resumes:
    analyze = st.button("🚀 Analyze Resumes")

    if analyze:
        with st.spinner("Analyzing resumes... This may take a moment ⏳"):
            jd_text = extract_text_from_pdf(jd_file)
            jd_info = extract_structured_info(jd_text, model=selected_model)

            st.subheader("📘 Extracted Job Description Summary")
            st.json(jd_info)

            results = []
            for resume in resumes:
                resume_text = extract_text_from_pdf(resume)
                resume_info = extract_structured_info(resume_text, model=selected_model)

                score, reason = weighted_similarity(
                    jd_info,
                    resume_info,
                    w_skills=w_skills,
                    w_experience=w_experience,
                    w_education=w_education,
                )
                fit_status = "FIT" if score >= 6.5 else "NOTFIT"

                results.append({
                    "Resume File": resume.name,
                    "Score": score,
                    "FIT/NOTFIT": fit_status,
                    "Reasoning": reason,
                })

            df = pd.DataFrame(results)
            st.success("✅ Analysis complete!")
            st.dataframe(df, width='stretch')

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("📥 Export Results (CSV)", data=csv, file_name="syncra_results.csv", mime="text/csv")

else:
    st.info("👈 Please upload both Job Description and Resumes to begin analysis.")
