"""
LLM enrichment: turn free-text reviews into queryable columns
=============================================================
Reads completed stays that have a real review, sends the review text to Gemini in
batches (one request = 25 reviews, typed JSON schema), and MERGEs the results into
NOMAD_HUB.AI.REVIEW_ENRICHMENTS. dbt then models that table into the AI marts.

  python ai/enrich_reviews.py --limit 500            # enrich 500 new reviews
  python ai/enrich_reviews.py --limit 50 --dry-run   # print results, write nothing

Design choices
- Idempotent: only reviews not yet in REVIEW_ENRICHMENTS are selected, and a failed
  batch is NOT written — it is simply picked up again next run (no fake "neutral" rows).
- Deterministic sample: ordered by a hash of review_id, so runs are reproducible.
  Half of each run comes from US stays where the guest flew in on a real BTS flight,
  which powers mart_delay_impact (does a delayed arrival show up in the review?).
- Rate limited for the free tier (--rpm), with exponential backoff on 429/5xx.
"""

import argparse
import json
import time
from typing import Literal

from google.genai import errors, types
from pydantic import BaseModel, Field

from common import GEMINI_ENRICH_MODEL, gemini, writer_connection

TOPICS = [
    "cleanliness", "location", "host_communication", "check_in", "value", "comfort",
    "noise", "amenities", "accuracy", "safety", "transport", "neighbourhood", "other",
]


class ReviewEnrichment(BaseModel):
    review_id: int
    language: str = Field(description="ISO 639-1 code of the review text, e.g. en, fr, ja")
    sentiment: Literal["positive", "neutral", "negative", "mixed"]
    sentiment_score: float = Field(description="-1.0 (very negative) to 1.0 (very positive)")
    topics: list[str] = Field(description=f"1-3 topics the guest talks about, from: {', '.join(TOPICS)}")
    complaint: str | None = Field(description="Main complaint in max 8 English words, or null if none")
    mentions_travel_disruption: bool = Field(
        description="True if the guest mentions a delayed/cancelled flight, late arrival or travel trouble")
    summary_en: str = Field(description="One-sentence English summary, max 25 words")


SYSTEM_PROMPT = f"""You analyse guest reviews of short-term rentals for a travel platform.
Reviews can be in any language. For EVERY review you receive, return one object with the
same review_id. Use only these topics: {", ".join(TOPICS)}.
sentiment_score: -1.0 very negative, 0 neutral, 1.0 very positive; "mixed" = clear praise
AND clear criticism. Write complaint and summary_en in English, whatever the review language."""

DDL = """
CREATE TABLE IF NOT EXISTS NOMAD_HUB.AI.REVIEW_ENRICHMENTS (
    REVIEW_ID                   NUMBER PRIMARY KEY,
    LANGUAGE                    VARCHAR(8),
    SENTIMENT                   VARCHAR(10),
    SENTIMENT_SCORE             FLOAT,
    TOPICS                      ARRAY,
    COMPLAINT                   VARCHAR,
    MENTIONS_TRAVEL_DISRUPTION  BOOLEAN,
    SUMMARY_EN                  VARCHAR,
    MODEL                       VARCHAR,
    ENRICHED_AT                 TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
) COMMENT = 'Gemini review enrichment, written by ai/enrich_reviews.py'
"""

# Unenriched reviews of completed stays; with_flight = guest flew in on a booked BTS flight.
CANDIDATES_SQL = """
SELECT r.review_id, r.comment_text
FROM NOMAD_HUB.MARTS.FCT_STAY_BOOKINGS s
JOIN NOMAD_HUB.STAGING.STG_AIRBNB__REVIEWS r ON r.review_id = s.review_id
WHERE NOT s.is_cancelled
  AND r.comment_length BETWEEN 30 AND 2000
  AND {flight_filter} EXISTS (
        SELECT 1 FROM NOMAD_HUB.MARTS.FCT_FLIGHT_BOOKINGS f
        WHERE f.stay_booking_id = s.stay_booking_id AND f.leg = 'outbound')
  AND NOT EXISTS (SELECT 1 FROM NOMAD_HUB.AI.REVIEW_ENRICHMENTS e WHERE e.review_id = r.review_id)
ORDER BY HASH(r.review_id)
LIMIT %(limit)s
"""

MERGE_SQL = """
MERGE INTO NOMAD_HUB.AI.REVIEW_ENRICHMENTS t
USING (
    SELECT review_id, language, sentiment, sentiment_score, PARSE_JSON(topics)::ARRAY AS topics,
           complaint, mentions_travel_disruption, summary_en, model
    FROM review_enrichments_batch
) s ON t.review_id = s.review_id
WHEN NOT MATCHED THEN INSERT
    (review_id, language, sentiment, sentiment_score, topics, complaint,
     mentions_travel_disruption, summary_en, model)
VALUES (s.review_id, s.language, s.sentiment, s.sentiment_score, s.topics, s.complaint,
        s.mentions_travel_disruption, s.summary_en, s.model)
"""


def fetch_candidates(cursor, limit: int) -> list[tuple[int, str]]:
    with_flight = limit // 2
    rows = cursor.execute(CANDIDATES_SQL.format(flight_filter=""), {"limit": with_flight}).fetchall()
    rows += cursor.execute(CANDIDATES_SQL.format(flight_filter="NOT"), {"limit": limit - len(rows)}).fetchall()
    return [(int(rid), text) for rid, text in rows]


def classify_batch(batch: list[tuple[int, str]], max_retries: int = 5) -> list[ReviewEnrichment]:
    payload = "\n\n".join(f"review_id: {rid}\ntext: {text}" for rid, text in batch)
    for attempt in range(max_retries):
        try:
            response = gemini().models.generate_content(
                model=GEMINI_ENRICH_MODEL,
                contents=payload,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=list[ReviewEnrichment],
                ),
            )
            results = response.parsed or []
            wanted = {rid for rid, _ in batch}
            clean = []
            for r in results:
                if r.review_id not in wanted:
                    continue                          # never trust ids we didn't send
                r.topics = [t for t in r.topics if t in TOPICS][:3] or ["other"]
                r.sentiment_score = max(-1.0, min(1.0, r.sentiment_score))
                clean.append(r)
            return clean
        except errors.APIError as exc:
            retryable = exc.code in (429, 500, 502, 503, 504)
            if not retryable or attempt == max_retries - 1:
                raise
            wait = 2 ** attempt * 10
            print(f"  ⚠ Gemini {exc.code}; retry in {wait}s")
            time.sleep(wait)
    return []


def save(conn, results: list[ReviewEnrichment]) -> int:
    cur = conn.cursor()
    cur.execute("""CREATE TEMPORARY TABLE IF NOT EXISTS review_enrichments_batch (
        review_id NUMBER, language VARCHAR, sentiment VARCHAR, sentiment_score FLOAT, topics VARCHAR,
        complaint VARCHAR, mentions_travel_disruption BOOLEAN, summary_en VARCHAR, model VARCHAR)""")
    cur.execute("TRUNCATE TABLE review_enrichments_batch")
    cur.executemany(
        "INSERT INTO review_enrichments_batch VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        [(r.review_id, r.language[:8], r.sentiment, r.sentiment_score, json.dumps(r.topics),
          r.complaint, r.mentions_travel_disruption, r.summary_en, GEMINI_ENRICH_MODEL) for r in results],
    )
    return cur.execute(MERGE_SQL).fetchone()[0]


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich reviews with Gemini")
    parser.add_argument("--limit", type=int, default=500, help="reviews to enrich this run")
    parser.add_argument("--batch-size", type=int, default=25, help="reviews per Gemini request")
    parser.add_argument("--rpm", type=float, default=8, help="max Gemini requests per minute")
    parser.add_argument("--dry-run", action="store_true", help="print, don't write")
    args = parser.parse_args()

    conn = writer_connection()
    cur = conn.cursor()
    cur.execute(DDL)
    reviews = fetch_candidates(cur, args.limit)
    print(f"Model {GEMINI_ENRICH_MODEL}: {len(reviews)} reviews to enrich in batches of {args.batch_size}")

    written, failed, last_call = 0, 0, 0.0
    for start in range(0, len(reviews), args.batch_size):
        batch = reviews[start:start + args.batch_size]
        time.sleep(max(0.0, 60 / args.rpm - (time.time() - last_call)))
        last_call = time.time()
        try:
            results = classify_batch(batch)
        except errors.APIError as exc:
            failed += len(batch)
            print(f"  ❌ batch {start // args.batch_size + 1}: {exc.code} {exc.message} — will retry next run")
            continue
        if args.dry_run:
            for r in results[:3]:
                print("   ", r.model_dump())
        else:
            written += save(conn, results)
        failed += len(batch) - len(results)
        print(f"  ✓ batch {start // args.batch_size + 1}: {len(results)}/{len(batch)} enriched")

    conn.close()
    print(f"Done: {written} written, {failed} not enriched (retried next run)")


if __name__ == "__main__":
    main()
