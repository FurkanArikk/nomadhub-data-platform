"""
NomadHub — AI Review Enrichment (Google Gemini)
================================================
Reads unenriched reviews from Snowflake STAGING.STG_REVIEWS,
calls Gemini 1.5 Flash in batch to extract structured insights,
and upserts results to NOMAD_HUB.AI.REVIEW_ENRICHED.

AI-extracted fields per review:
  - sentiment          : positive / neutral / negative
  - sentiment_score    : float 0.0–1.0
  - category           : flight_service / hotel_comfort / location / staff / value / food / cleanliness
  - travel_type        : business / leisure / family / solo / honeymoon
  - summary            : 1-2 sentence summary
  - key_topics         : JSON array of up to 5 key topics
  - service_score      : 1–5
  - value_score        : 1–5
  - location_score     : 1–5
  - cleanliness_score  : 1–5
  - staff_score        : 1–5

Usage:
    python enrich_reviews.py                     # enrich all unenriched
    python enrich_reviews.py --limit 1000        # process N reviews
    python enrich_reviews.py --batch-size 50     # custom batch size
    python enrich_reviews.py --dry-run           # test without writing to Snowflake
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import google.generativeai as genai
import pandas as pd
import snowflake.connector
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Gemini setup ──────────────────────────────────────────────────────────────

genai.configure(api_key=os.environ["GEMINI_API_KEY"])
MODEL = genai.GenerativeModel(
    model_name="gemini-1.5-flash",
    generation_config=genai.GenerationConfig(
        temperature=0.1,          # low temp for structured extraction
        response_mime_type="application/json",
    ),
)

ENRICHMENT_PROMPT = """
You are a travel review analyst. Given a travel review, extract structured insights.
Return ONLY valid JSON (no markdown, no extra text).

Review:
Title: {title}
Type: {review_type}
Rating: {rating}/5
Text: {text}

Return this exact JSON structure:
{{
  "sentiment": "positive" | "neutral" | "negative",
  "sentiment_score": <float 0.0-1.0, where 1.0=most positive>,
  "category": "flight_service" | "hotel_comfort" | "location" | "staff" | "value" | "food" | "cleanliness",
  "travel_type": "business" | "leisure" | "family" | "solo" | "honeymoon" | "unknown",
  "summary": "<1-2 sentence neutral summary of the review>",
  "key_topics": ["<topic1>", "<topic2>", ...(max 5)],
  "service_score": <int 1-5 or null if not applicable>,
  "value_score": <int 1-5>,
  "location_score": <int 1-5 or null if not applicable>,
  "cleanliness_score": <int 1-5 or null if review_type is 'flight'>,
  "staff_score": <int 1-5>
}}
"""


# ── Snowflake setup ───────────────────────────────────────────────────────────

def get_snowflake_conn():
    return snowflake.connector.connect(
        account   = os.environ["SNOWFLAKE_ACCOUNT"],
        user      = os.environ["SNOWFLAKE_USER"],
        password  = os.environ["SNOWFLAKE_PASSWORD"],
        database  = "NOMAD_HUB",
        schema    = "AI",
        warehouse = "NOMAD_WH",
        role      = "DBT_ROLE",
    )


def ensure_target_table(conn) -> None:
    """Create AI.REVIEW_ENRICHED if it doesn't exist."""
    ddl = """
    CREATE TABLE IF NOT EXISTS NOMAD_HUB.AI.REVIEW_ENRICHED (
        REVIEW_ID           NUMBER          PRIMARY KEY,
        AI_SENTIMENT        VARCHAR(10),
        AI_SENTIMENT_SCORE  FLOAT,
        AI_CATEGORY         VARCHAR(30),
        AI_TRAVEL_TYPE      VARCHAR(20),
        AI_SUMMARY          VARCHAR(1000),
        AI_KEY_TOPICS       VARIANT,
        AI_SERVICE_SCORE    NUMBER(1),
        AI_VALUE_SCORE      NUMBER(1),
        AI_LOCATION_SCORE   NUMBER(1),
        AI_CLEANLINESS_SCORE NUMBER(1),
        AI_STAFF_SCORE      NUMBER(1),
        ENRICHED_AT         TIMESTAMP_NTZ
    ) COMMENT = 'Gemini-enriched travel review insights'
    """
    conn.cursor().execute(ddl)
    log.info("✅ AI.REVIEW_ENRICHED table ready")


def fetch_unenriched_reviews(conn, limit: int | None) -> pd.DataFrame:
    """Fetch reviews that haven't been enriched yet."""
    limit_clause = f"LIMIT {limit}" if limit else ""
    query = f"""
    SELECT
        r.REVIEW_ID,
        r.REVIEW_TYPE,
        r.REVIEW_TITLE,
        r.REVIEW_TEXT,
        r.RATING
    FROM NOMAD_HUB.STAGING.STG_REVIEWS r
    LEFT JOIN NOMAD_HUB.AI.REVIEW_ENRICHED e
        ON r.REVIEW_ID = e.REVIEW_ID
    WHERE e.REVIEW_ID IS NULL
      AND r.REVIEW_TEXT IS NOT NULL
      AND LENGTH(r.REVIEW_TEXT) >= 20
    ORDER BY r.REVIEW_ID
    {limit_clause}
    """
    return pd.read_sql(query, conn)


def enrich_batch(batch: list[dict]) -> list[dict]:
    """Call Gemini to enrich a batch of reviews."""
    results = []
    for review in batch:
        prompt = ENRICHMENT_PROMPT.format(
            title       = review.get("REVIEW_TITLE", ""),
            review_type = review.get("REVIEW_TYPE", "unknown"),
            rating      = review.get("RATING", 3),
            text        = review["REVIEW_TEXT"][:2000],  # truncate very long texts
        )
        try:
            response = MODEL.generate_content(prompt)
            parsed = json.loads(response.text)
            parsed["review_id"] = review["REVIEW_ID"]
            parsed["error"] = None
        except json.JSONDecodeError as e:
            log.warning(f"JSON parse error for review {review['REVIEW_ID']}: {e}")
            parsed = _fallback_result(review["REVIEW_ID"])
        except Exception as e:
            log.warning(f"Gemini error for review {review['REVIEW_ID']}: {e}")
            parsed = _fallback_result(review["REVIEW_ID"])

        results.append(parsed)

        # Rate limiting: ~30 req/min on free tier → ~2s between calls
        time.sleep(0.5)

    return results


def _fallback_result(review_id: int) -> dict:
    """Default result when Gemini call fails."""
    return {
        "review_id": review_id,
        "sentiment": "neutral",
        "sentiment_score": 0.5,
        "category": "unknown",
        "travel_type": "unknown",
        "summary": "Unable to process review.",
        "key_topics": [],
        "service_score": None,
        "value_score": None,
        "location_score": None,
        "cleanliness_score": None,
        "staff_score": None,
        "error": "gemini_error",
    }


def upsert_results(conn, results: list[dict], dry_run: bool = False) -> int:
    """Upsert enriched results into AI.REVIEW_ENRICHED."""
    if dry_run:
        log.info(f"[DRY RUN] Would upsert {len(results)} rows")
        return len(results)

    enriched_at = datetime.now(timezone.utc)
    rows = []
    for r in results:
        rows.append((
            r["review_id"],
            r.get("sentiment"),
            r.get("sentiment_score"),
            r.get("category"),
            r.get("travel_type"),
            r.get("summary"),
            json.dumps(r.get("key_topics", [])),
            r.get("service_score"),
            r.get("value_score"),
            r.get("location_score"),
            r.get("cleanliness_score"),
            r.get("staff_score"),
            enriched_at,
        ))

    merge_sql = """
    MERGE INTO NOMAD_HUB.AI.REVIEW_ENRICHED AS target
    USING (
        SELECT
            column1::NUMBER          AS review_id,
            column2::VARCHAR(10)     AS ai_sentiment,
            column3::FLOAT           AS ai_sentiment_score,
            column4::VARCHAR(30)     AS ai_category,
            column5::VARCHAR(20)     AS ai_travel_type,
            column6::VARCHAR(1000)   AS ai_summary,
            PARSE_JSON(column7)      AS ai_key_topics,
            column8::NUMBER(1)       AS ai_service_score,
            column9::NUMBER(1)       AS ai_value_score,
            column10::NUMBER(1)      AS ai_location_score,
            column11::NUMBER(1)      AS ai_cleanliness_score,
            column12::NUMBER(1)      AS ai_staff_score,
            column13::TIMESTAMP_NTZ  AS enriched_at
        FROM VALUES {placeholders}
    ) AS source ON target.review_id = source.review_id
    WHEN MATCHED THEN UPDATE SET
        ai_sentiment        = source.ai_sentiment,
        ai_sentiment_score  = source.ai_sentiment_score,
        ai_category         = source.ai_category,
        ai_travel_type      = source.ai_travel_type,
        ai_summary          = source.ai_summary,
        ai_key_topics       = source.ai_key_topics,
        ai_service_score    = source.ai_service_score,
        ai_value_score      = source.ai_value_score,
        ai_location_score   = source.ai_location_score,
        ai_cleanliness_score= source.ai_cleanliness_score,
        ai_staff_score      = source.ai_staff_score,
        enriched_at         = source.enriched_at
    WHEN NOT MATCHED THEN INSERT (
        review_id, ai_sentiment, ai_sentiment_score, ai_category, ai_travel_type,
        ai_summary, ai_key_topics, ai_service_score, ai_value_score, ai_location_score,
        ai_cleanliness_score, ai_staff_score, enriched_at
    ) VALUES (
        source.review_id, source.ai_sentiment, source.ai_sentiment_score, source.ai_category,
        source.ai_travel_type, source.ai_summary, source.ai_key_topics, source.ai_service_score,
        source.ai_value_score, source.ai_location_score, source.ai_cleanliness_score,
        source.ai_staff_score, source.enriched_at
    )
    """

    # Snowflake VALUES placeholder
    placeholders = ", ".join(["(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)"] * len(rows))
    flat_values = [v for row in rows for v in row]

    cursor = conn.cursor()
    cursor.execute(merge_sql.format(placeholders=placeholders), flat_values)
    return cursor.rowcount


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="NomadHub review enrichment via Gemini")
    parser.add_argument("--limit", type=int, help="Max reviews to enrich in this run")
    parser.add_argument("--batch-size", type=int, default=20, help="Gemini batch size (default: 20)")
    parser.add_argument("--dry-run", action="store_true", help="Run without writing to Snowflake")
    args = parser.parse_args()

    log.info("=" * 60)
    log.info("  NomadHub Review Enrichment — Google Gemini 1.5 Flash")
    log.info("=" * 60)

    conn = get_snowflake_conn()

    if not args.dry_run:
        ensure_target_table(conn)

    # Fetch unenriched reviews
    log.info(f"Fetching unenriched reviews (limit={args.limit or 'all'})...")
    df = fetch_unenriched_reviews(conn, args.limit)
    log.info(f"  → Found {len(df):,} reviews to enrich")

    if len(df) == 0:
        log.info("✅ No new reviews to enrich. All up-to-date.")
        return

    # Process in batches
    records = df.to_dict("records")
    total_upserted = 0

    batches = [records[i:i + args.batch_size] for i in range(0, len(records), args.batch_size)]
    for batch in tqdm(batches, desc="Enriching batches", unit="batch"):
        enriched = enrich_batch(batch)
        n = upsert_results(conn, enriched, dry_run=args.dry_run)
        total_upserted += len(enriched)

    log.info(f"\n✅ Enrichment complete: {total_upserted:,} reviews processed")
    log.info("   Run dbt to materialise mart_review_insights:")
    log.info("   dbt run --select mart_review_insights")
    conn.close()


if __name__ == "__main__":
    main()
