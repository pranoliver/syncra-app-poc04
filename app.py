import streamlit as st
import pandas as pd
import base64
import io
import os
from utils import (
    extract_text_from_pdf,
    get_embedding_ollama,
    get_embedding_minilm,
    compute_similarity,
    generate_reasoning,
    list_ollama_models,
    clear_all_cache,
    cache,
)

# ---------------------------------------------
# PAGE CONFIG
# ---------------------------------------------
st.set_page_config(page_title="Syncra - AI Resume Matcher", layout="wide")

def load_js(file_name: str):
    with open(file_name) as f:
        return f"<script>{f.read()}</script>"

# ---------------------------------------------
# LOAD LOGO
# ---------------------------------------------
with open("syncra_logo_01.png", "rb") as f:
    logo_base64 = base64.b64encode(f.read()).decode("utf-8")

# ---------------------------------------------
# LOAD THEME CSS
# ---------------------------------------------
def local_css(file_name: str):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

local_css("theme.css")

# ---------------------------------------------
# SIDEBAR CONFIG (with styled sections)
# ---------------------------------------------
st.sidebar.markdown("### 🗂️ Inputs")
jd_file = st.sidebar.file_uploader("Upload Job Description (PDF)", type=["pdf"])
resumes = st.sidebar.file_uploader(
    "Upload Candidate Resumes (PDF)", type=["pdf"], accept_multiple_files=True
)

st.sidebar.markdown("### 🤖 Model Selection")
available_models = list_ollama_models()
st.markdown(
    """
    <style>
    /* Target the label of the selectbox */
    div[data-testid="stMarkdownContainer"] p { /* Adjust the selector if necessary based on your Streamlit version and specific layout */
        color: white; /* Change to your desired color */
    }
    </style>
    """,
    unsafe_allow_html=True,
)
default_index_model = available_models.index('mistral:latest')
selected_model = st.sidebar.selectbox("Select Local LLM Model", available_models, index=default_index_model)

st.sidebar.markdown("### 🧠 Embedding Options")
embedder_choice = st.sidebar.selectbox(
    "Select Embedding Method",
    ["🧠 Ollama Embeddings", "🧩 MiniLM (Local Transformer)"],
    index=1,
)
st.session_state["embedder_choice"] = embedder_choice

# --- Analyze Button (moved just below embedder selector) ---
if st.sidebar.button("🚀 Analyze Matches", use_container_width=True):
    st.session_state["analyzing"] = True
    st.session_state["selected_model"] = selected_model
    st.rerun()

st.sidebar.markdown("### ⚙️ Cache Controls")

# --- Clear Cache Button ---
if st.sidebar.button("🧹 Clear Cache", use_container_width=True):
    msg = clear_all_cache()
    st.sidebar.success(msg)
    st.session_state["cache_cleared"] = True
    st.rerun()

# --- Cache Summary ---
def render_cache_summary():
    try:
        cache_size = sum(
            os.path.getsize(os.path.join(cache.directory, f))
            for f in os.listdir(cache.directory)
        ) / (1024 * 1024)
        st.sidebar.caption(f"🗂️ Cached Items: {len(cache)} | Size: {cache_size:.2f} MB")
    except Exception:
        st.sidebar.caption("🗂️ Cache summary unavailable")

# ---------------------------------------------
# HEADER SECTION
# ---------------------------------------------
MODEL_COLORS = {
    "mistral": "#38bdf8",
    "llama": "#facc15",
    "phi": "#22c55e",
    "qwen": "#ec4899",
    "gemma": "#8b5cf6",
}
model_key = selected_model.split(":")[0].lower()
indicator_color = MODEL_COLORS.get(model_key, "#93c5fd")

st.markdown(
    f"<style>:root {{ --indicator-color: {indicator_color}; }}</style>",
    unsafe_allow_html=True,
)

is_syncing = st.session_state.get("analyzing", False)
sync_indicator_html = '<div class="syncra-dot"></div>' if is_syncing else "<div></div>"

# ---------------------------------------------
# HEADER & TAGLINE BELOW SIDEBAR
# ---------------------------------------------
st.markdown(
    f"""
    <div class="syncra-header" style="margin-top: 1rem;">
        <div style="display: flex; align-items: center; gap: 12px;">
            <img src="data:image/png;base64,{logo_base64}" alt="Syncra Logo" class="syncra-logo" />
            {sync_indicator_html}
        </div>
        <div class="syncra-caption" style="margin-top: 8px;">
            Elegant, Explainable, and Entirely Local
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# Page Title
st.markdown(
    "<h2 style='margin-top: 1.5rem;'>📊 Syncra Resume Match Result</h2>",
    unsafe_allow_html=True,
)

# ---------------------------------------------
# LOADING OVERLAY
# ---------------------------------------------
if st.session_state.get("analyzing", False):
    st.markdown(
        """
        <div class="overlay">
            <div class="spinner"></div>
            <p>Analyzing resumes with local LLM...</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

results = []

# ---------------------------------------------
# ANALYSIS LOGIC
# ---------------------------------------------
if st.session_state.get("analyzing", False):
    if not jd_file:
        st.error("Please upload a Job Description PDF.")
        st.session_state["analyzing"] = False
    elif not resumes:
        st.error("Please upload at least one resume.")
        st.session_state["analyzing"] = False
    else:
        jd_text = extract_text_from_pdf(jd_file)
        with st.expander("📄 View Job Description"):
            st.write(jd_text)

        # Choose embedder dynamically
        if st.session_state["embedder_choice"] == "🧩 MiniLM (Local Transformer)":
            jd_embedding = get_embedding_minilm(jd_text)
        else:
            jd_embedding = get_embedding_ollama(jd_text)

        for resume in resumes:
            resume_text = extract_text_from_pdf(resume)
            if st.session_state["embedder_choice"] == "🧩 MiniLM (Local Transformer)":
                resume_emb = get_embedding_minilm(resume_text)
            else:
                resume_emb = get_embedding_ollama(resume_text)

            similarity_score = compute_similarity(jd_embedding, resume_emb)
            reasoning = generate_reasoning(jd_text, resume_text, model=selected_model)
            fit_status = "FIT" if similarity_score >= 6.5 else "NOTFIT"

            results.append({
                "Resume File": resume.name,
                "Score": similarity_score,
                "FIT/NOTFIT": fit_status,
                "Reasoning": reasoning,
            })

        st.session_state["results"] = results
        st.session_state["analyzing"] = False
        st.session_state["cache_cleared"] = False
        st.rerun()

# ---------------------------------------------
# RESULTS DISPLAY
# ---------------------------------------------
# ---------------------------
# RESULTS DISPLAY (robust)
# ---------------------------
results_list = st.session_state.get("results", [])

# Quick debug/visibility: show when results exist but table empty locally
if st.session_state.get("analyzing", False):
    st.info("Analysis in progress...")

if not results_list:
    st.info("No results yet. Run analysis to see the consolidated table below.")
else:
    # show count so we can tell if results arrived
    st.info(f"Found {len(results_list)} result(s) in session state.")
    # st.caption(f"Found {len(results_list)} result(s) in session state.")

    # Legend (score color guide)
    legend_html = """
    <div class="score-legend">
        <span class="legend-item"><span class="legend-dot high"></span> High (8 - 10)</span>
        <span class="legend-item"><span class="legend-dot medium"></span> Medium (5 - 7.9)</span>
        <span class="legend-item"><span class="legend-dot low"></span> Low (1 - 4.9)</span>
    </div>
    """
    st.markdown(legend_html, unsafe_allow_html=True)

    # Build table head
    table_html = '<table class="syncra-table"><thead>'
    table_html += '<tr><th>Resume File</th><th>Score</th><th>FIT/NOTFIT</th><th>Reasoning</th>'
    table_html += '</tr></thead><tbody>'

    # Append rows from session-state results (guaranteed to be present if we got here)
    for row in results_list:
        badge_class = "fit-badge" if row.get("FIT/NOTFIT") == "FIT" else "notfit-badge"

        score = row.get("Score", 0)
        if score >= 8:
            score_color = "score-high"
        elif score >= 5:
            score_color = "score-medium"
        else:
            score_color = "score-low"

        # ensure proper escaping of HTML-sensitive content (basic)
        resume_name = str(row.get("Resume File", "")).replace("<", "&lt;").replace(">", "&gt;")
        reasoning = str(row.get("Reasoning", "")).replace("<", "&lt;").replace(">", "&gt;")
        reasoning_full = str(row.get("Reasoning", "")).replace("<", "&lt;").replace(">", "&gt;")
        reasoning_preview = reasoning_full[:120] + ("..." if len(reasoning_full) > 120 else "")

        table_html += '<tr style="max-height: 100px !important;">'
        table_html += f'<td><span class="result-text">{resume_name}</span</td>'
        table_html += f'<td><span class="{score_color}">{score:.2f}</span></td>'
        table_html += f'<td><span class="{badge_class}">{row.get("FIT/NOTFIT", "")}</span></td>'
        table_html += f'<td><div class="result-text">{reasoning}</div></td></tr>'
        # table_html += f'<td><div class="reasoning-cell"><span class="preview">{reasoning_preview}</span><span class="full-text" style="display:none;">{reasoning_full}</span><a href="#" class="toggle-link">Show more</a></div>'

    # close table
    table_html += '</tbody></table>'
    # Load external JS file (from local directory)
    with open("script.js", "r") as js_file:
        custom_js = js_file.read()

    # Sortable JS integration
    sortable_table_html = f'<div id="sortable-table">{table_html}</div>'
    # sortable_table_html += f'<script>{custom_js}</script>'
    st.markdown(sortable_table_html, unsafe_allow_html=True)

    # CSV Export right below
    try:
        import pandas as _pd, io as _io
        _df = _pd.DataFrame(results_list)
        csv_buffer = _io.StringIO()
        _df.to_csv(csv_buffer, index=False)
        st.download_button(
            label="📥 Download Results (CSV)",
            data=csv_buffer.getvalue(),
            file_name="Syncra_Results.csv",
            mime="text/csv",
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"CSV export failed: {e}")

# Sidebar cache info refresh
st.sidebar.divider()
render_cache_summary()
