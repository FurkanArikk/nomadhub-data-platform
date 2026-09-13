"""
NomadHub — RAG Chat: "Chat with Your Travel Reviews"
======================================================
Embeds travel reviews using Google text-embedding-004,
stores vectors in a local FAISS index,
and answers questions using Gemini 1.5 Flash with retrieved context.

Run: streamlit run rag_chat.py
"""

import json
import os
import pickle
from pathlib import Path

import faiss
import numpy as np
import pandas as pd
import snowflake.connector
import streamlit as st
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# ── Config ────────────────────────────────────────────────────────────────────
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
EMBED_MODEL = "models/text-embedding-004"
CHAT_MODEL  = genai.GenerativeModel("gemini-1.5-flash")
INDEX_PATH  = Path(__file__).parent / "review_vectors.faiss"
META_PATH   = Path(__file__).parent / "review_vectors.pkl"
TOP_K       = 5


# ── Snowflake ─────────────────────────────────────────────────────────────────
@st.cache_resource
def get_conn():
    return snowflake.connector.connect(
        account   = os.environ["SNOWFLAKE_ACCOUNT"],
        user      = os.environ["SNOWFLAKE_USER"],
        password  = os.environ["SNOWFLAKE_PASSWORD"],
        database  = "NOMAD_HUB",
        schema    = "STAGING",
        warehouse = "NOMAD_WH",
        role      = "ANALYST_ROLE",
    )


@st.cache_data(ttl=3600, show_spinner="Loading reviews from Snowflake...")
def load_reviews() -> pd.DataFrame:
    conn = get_conn()
    query = """
    SELECT
        review_id,
        entity_name,
        destination_city,
        review_type,
        rating,
        review_title,
        review_text,
        review_date,
        language
    FROM NOMAD_HUB.STAGING.STG_REVIEWS
    WHERE review_text IS NOT NULL
      AND LENGTH(review_text) >= 20
    LIMIT 10000
    ORDER BY helpful_votes DESC NULLS LAST
    """
    return pd.read_sql(query, conn)


# ── Embedding & Index ─────────────────────────────────────────────────────────

def embed_texts(texts: list[str]) -> np.ndarray:
    """Embed a list of texts using Gemini text-embedding-004."""
    results = genai.embed_content(
        model=EMBED_MODEL,
        content=texts,
        task_type="retrieval_document",
    )
    return np.array(results["embedding"], dtype=np.float32)


def build_index(df: pd.DataFrame) -> tuple[faiss.Index, list[dict]]:
    """Build FAISS index from review texts."""
    texts = (
        df["review_title"].fillna("") + " | " + df["review_text"].fillna("")
    ).tolist()

    st.info(f"Building vector index for {len(texts):,} reviews... (first time only)")

    # Embed in batches of 100 (Gemini batch limit)
    all_embeddings = []
    batch_size = 100
    progress = st.progress(0)
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        emb = embed_texts(batch)
        all_embeddings.append(emb)
        progress.progress(min(i / len(texts), 1.0))
    progress.empty()

    embeddings = np.vstack(all_embeddings)
    dim = embeddings.shape[1]

    # FAISS flat L2 index
    index = faiss.IndexFlatL2(dim)
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(dim)  # Inner product (cosine similarity after L2-norm)
    index.add(embeddings)

    # Metadata for retrieval
    metadata = df[["review_id", "entity_name", "destination_city",
                   "review_type", "rating", "review_date"]].to_dict("records")

    faiss.write_index(index, str(INDEX_PATH))
    with open(META_PATH, "wb") as f:
        pickle.dump({"metadata": metadata, "texts": texts}, f)

    return index, metadata, texts


@st.cache_resource
def load_or_build_index(df: pd.DataFrame):
    if INDEX_PATH.exists() and META_PATH.exists():
        index = faiss.read_index(str(INDEX_PATH))
        with open(META_PATH, "rb") as f:
            store = pickle.load(f)
        return index, store["metadata"], store["texts"]
    return build_index(df)


# ── Retrieval ─────────────────────────────────────────────────────────────────

def retrieve(query: str, index, metadata: list[dict], texts: list[str]) -> list[dict]:
    """Embed query and retrieve top-K similar reviews."""
    q_emb = embed_texts([query])
    faiss.normalize_L2(q_emb)
    scores, indices = index.search(q_emb, TOP_K)

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx < 0:
            continue
        results.append({
            "text": texts[idx],
            "score": float(score),
            **metadata[idx],
        })
    return results


def generate_answer(question: str, retrieved: list[dict]) -> str:
    """Generate a grounded answer using retrieved reviews as context."""
    context_parts = []
    for i, r in enumerate(retrieved, 1):
        context_parts.append(
            f"[Review {i}] Entity: {r['entity_name']} | "
            f"Destination: {r['destination_city']} | "
            f"Type: {r['review_type']} | Rating: {r['rating']}/5\n"
            f"{r['text']}"
        )
    context = "\n\n".join(context_parts)

    prompt = f"""You are a helpful travel advisor with access to real customer reviews from NomadHub.
Answer the user's question based ONLY on the provided reviews. 
If the reviews don't contain enough information, say so honestly.
Always cite which review(s) you're drawing from (e.g., "According to Review 2...").

Customer Reviews:
{context}

User Question: {question}

Answer:"""

    response = CHAT_MODEL.generate_content(prompt)
    return response.text


# ── Streamlit UI ──────────────────────────────────────────────────────────────

def main():
    st.set_page_config(
        page_title="NomadHub — Chat with Reviews",
        page_icon="✈️",
        layout="wide",
    )

    # Header
    st.markdown("""
    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 2rem; border-radius: 12px; margin-bottom: 2rem;">
        <h1 style="color: white; margin: 0; font-size: 2rem;">✈️ NomadHub Review Chat</h1>
        <p style="color: rgba(255,255,255,0.85); margin: 0.5rem 0 0 0; font-size: 1.1rem;">
            Ask questions about travel experiences — powered by Google Gemini RAG
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Load data and build index
    with st.spinner("Loading review database..."):
        df = load_reviews()

    index, metadata, texts = load_or_build_index(df)

    col1, col2, col3 = st.columns(3)
    col1.metric("📝 Reviews Indexed", f"{len(df):,}")
    col2.metric("🌍 Destinations", df["destination_city"].nunique())
    col3.metric("⭐ Avg Rating", f"{df['rating'].mean():.1f}/5")

    st.divider()

    # Example questions
    st.markdown("**💡 Try asking:**")
    example_questions = [
        "What do travellers say about business class flights?",
        "Which hotels are best for families?",
        "What are common complaints about budget hotels?",
        "What makes travellers rate a destination 5 stars?",
    ]
    cols = st.columns(len(example_questions))
    for col, q in zip(cols, example_questions):
        if col.button(q, use_container_width=True):
            st.session_state["question"] = q

    # Chat input
    question = st.text_input(
        "Ask about travel reviews...",
        value=st.session_state.get("question", ""),
        placeholder="e.g. What airlines do business travellers prefer?",
        key="user_question",
    )

    if question:
        with st.spinner("Searching reviews and generating answer..."):
            retrieved = retrieve(question, index, metadata, texts)
            answer = generate_answer(question, retrieved)

        # Answer
        st.markdown("### 🤖 Answer")
        st.markdown(f"""
        <div style="background: #f0f7ff; border-left: 4px solid #667eea;
                    padding: 1rem 1.5rem; border-radius: 8px;">
            {answer}
        </div>
        """, unsafe_allow_html=True)

        # Source reviews
        with st.expander("📚 Source Reviews Used", expanded=False):
            for i, r in enumerate(retrieved, 1):
                st.markdown(f"""
                **[Review {i}]** ⭐ {r['rating']}/5 | 📍 {r['destination_city']} | 
                🏷️ {r['entity_name']} | 📅 {r['review_date']} | 
                Relevance: {r['score']:.3f}
                """)
                st.caption(r["text"])
                if i < len(retrieved):
                    st.divider()


if __name__ == "__main__":
    main()
