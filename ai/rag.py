"""
RAG — "chat with the reviews", with the vector index inside Snowflake
=====================================================================
Reviews are embedded with Gemini and stored in NOMAD_HUB.AI.REVIEW_EMBEDDINGS as a
native VECTOR(FLOAT, 768) column. Retrieval is a SQL query ranked by
VECTOR_COSINE_SIMILARITY — no separate vector database, and it respects the same
roles and grants as the rest of the warehouse.

  python ai/rag.py index --limit 20000        # embed reviews (incremental)
  python ai/rag.py ask "Is Tokyo noisy at night?" --city tokyo

The Streamlit app imports search() and answer() from here.
"""

import argparse
import json
import time

from google.genai import errors, types

from common import (
    EMBED_DIM,
    GEMINI_EMBED_MODEL,
    GEMINI_MODEL,
    gemini,
    reader_connection,
    writer_connection,
)
from enrich_reviews import DDL as ENRICHMENTS_DDL

DDL = f"""
CREATE TABLE IF NOT EXISTS NOMAD_HUB.AI.REVIEW_EMBEDDINGS (
    REVIEW_ID       NUMBER PRIMARY KEY,
    LISTING_ID      NUMBER,
    CITY            VARCHAR,
    REVIEW_DATE     DATE,
    COMMENT_TEXT    VARCHAR,
    EMBEDDING       VECTOR(FLOAT, {EMBED_DIM}),
    MODEL           VARCHAR,
    EMBEDDED_AT     TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
) COMMENT = 'Gemini embeddings of review text for RAG, written by ai/rag.py'
"""

# Spread the index across cities and years; reviews already enriched by the LLM go
# first so RAG answers and the enrichment marts talk about the same reviews.
CANDIDATES_SQL = """
SELECT r.review_id, r.listing_id, r.city, r.review_date, r.comment_text
FROM NOMAD_HUB.STAGING.STG_AIRBNB__REVIEWS r
LEFT JOIN NOMAD_HUB.AI.REVIEW_ENRICHMENTS e ON e.review_id = r.review_id
WHERE r.comment_length BETWEEN 40 AND 2000
  AND r.review_date >= '2019-01-01'
  AND NOT EXISTS (SELECT 1 FROM NOMAD_HUB.AI.REVIEW_EMBEDDINGS x WHERE x.review_id = r.review_id)
QUALIFY ROW_NUMBER() OVER (PARTITION BY r.city ORDER BY e.review_id IS NULL, HASH(r.review_id))
        <= %(per_city)s
"""


def embed(texts: list[str], task_type: str) -> list[list[float]]:
    for attempt in range(5):
        try:
            result = gemini().models.embed_content(
                model=GEMINI_EMBED_MODEL,
                contents=texts,
                config=types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBED_DIM),
            )
            return [e.values for e in result.embeddings]
        except errors.APIError as exc:
            if exc.code not in (429, 500, 503) or attempt == 4:
                raise
            time.sleep(2 ** attempt * 10)
    return []


def build_index(limit: int, batch_size: int = 100, rpm: float = 30) -> None:
    conn = writer_connection()
    cur = conn.cursor()
    cur.execute(DDL)
    cur.execute(ENRICHMENTS_DDL)   # the candidate query prefers already-enriched reviews
    cur.execute("SELECT COUNT(DISTINCT city) FROM NOMAD_HUB.STAGING.STG_AIRBNB__LISTINGS")
    per_city = max(1, limit // cur.fetchone()[0])
    rows = cur.execute(CANDIDATES_SQL, {"per_city": per_city}).fetchall()
    print(f"Embedding {len(rows)} reviews with {GEMINI_EMBED_MODEL} ({EMBED_DIM} dims)")

    cur.execute("""CREATE TEMPORARY TABLE IF NOT EXISTS review_embeddings_batch (
        review_id NUMBER, listing_id NUMBER, city VARCHAR, review_date DATE,
        comment_text VARCHAR, embedding_json VARCHAR)""")
    last_call = 0.0
    for start in range(0, len(rows), batch_size):
        batch = rows[start:start + batch_size]
        time.sleep(max(0.0, 60 / rpm - (time.time() - last_call)))
        last_call = time.time()
        vectors = embed([r[4] for r in batch], "RETRIEVAL_DOCUMENT")
        cur.execute("TRUNCATE TABLE review_embeddings_batch")
        cur.executemany(
            "INSERT INTO review_embeddings_batch VALUES (%s, %s, %s, %s, %s, %s)",
            [(*r, json.dumps(v)) for r, v in zip(batch, vectors, strict=True)],
        )
        cur.execute(f"""
            INSERT INTO NOMAD_HUB.AI.REVIEW_EMBEDDINGS
                (review_id, listing_id, city, review_date, comment_text, embedding, model)
            SELECT review_id, listing_id, city, review_date, comment_text,
                   PARSE_JSON(embedding_json)::ARRAY::VECTOR(FLOAT, {EMBED_DIM}), %s
            FROM review_embeddings_batch
        """, (GEMINI_EMBED_MODEL,))
        print(f"  ✓ {min(start + batch_size, len(rows))}/{len(rows)}")
    conn.close()


def search(question: str, k: int = 8, city: str | None = None, conn=None) -> list[dict]:
    """Top-k reviews by cosine similarity, computed inside Snowflake."""
    query_vector = embed([question], "RETRIEVAL_QUERY")[0]
    own_conn = conn is None
    conn = conn or reader_connection("AI")
    cur = conn.cursor()
    cur.execute(f"""
        SELECT review_id, city, review_date, comment_text,
               VECTOR_COSINE_SIMILARITY(embedding, PARSE_JSON(%(q)s)::ARRAY::VECTOR(FLOAT, {EMBED_DIM})) AS score
        FROM NOMAD_HUB.AI.REVIEW_EMBEDDINGS
        WHERE %(city)s IS NULL OR city = %(city)s
        ORDER BY score DESC
        LIMIT %(k)s
    """, {"q": json.dumps(query_vector), "city": city, "k": k})
    cols = [c[0].lower() for c in cur.description]
    hits = [dict(zip(cols, row, strict=True)) for row in cur.fetchall()]
    if own_conn:
        conn.close()
    return hits


def answer(question: str, hits: list[dict]) -> str:
    """Answer grounded ONLY in the retrieved reviews, citing them as [1], [2], …"""
    context = "\n\n".join(
        f"[{i}] ({h['city']}, {h['review_date']}) {h['comment_text']}" for i, h in enumerate(hits, 1)
    )
    response = gemini().models.generate_content(
        model=GEMINI_MODEL,
        contents=f"Question: {question}\n\nGuest reviews:\n{context}",
        config=types.GenerateContentConfig(
            temperature=0.2,
            system_instruction=(
                "You answer questions about short-term rental stays using ONLY the guest reviews "
                "provided. Cite the reviews you use as [n]. Reviews may be in any language; answer "
                "in the language of the question. If the reviews don't answer it, say so."
            ),
        ),
    )
    return response.text


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG over reviews (Snowflake VECTOR + Gemini)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_index = sub.add_parser("index", help="embed reviews into AI.REVIEW_EMBEDDINGS")
    p_index.add_argument("--limit", type=int, default=20000)
    p_index.add_argument("--rpm", type=float, default=30)
    p_ask = sub.add_parser("ask", help="ask a question")
    p_ask.add_argument("question")
    p_ask.add_argument("--city")
    p_ask.add_argument("-k", type=int, default=8)
    args = parser.parse_args()

    if args.cmd == "index":
        build_index(args.limit, rpm=args.rpm)
    else:
        hits = search(args.question, args.k, args.city)
        print(answer(args.question, hits), "\n")
        for i, h in enumerate(hits, 1):
            print(f"[{i}] {h['score']:.3f} {h['city']} {h['review_date']}: {h['comment_text'][:110]}")


if __name__ == "__main__":
    main()
