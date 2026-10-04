# Architecture diagram — layout spec

Box-by-box content for redrawing `docs/architecture.png` in the same layout as the
reference project's diagram (Figma / Excalidraw / draw.io). Export the result to
`docs/architecture.png`; the README already links it.

Canvas ≈ 1680 × 950 px, light background. Five bands top to bottom:
pipeline row → AI lane → orchestration → foundation & tools.

---

## Band 1 — pipeline (6 boxes, left → right, arrows between)

| # | Header (colour) | Icon | Title | Body (2–3 short lines) |
|---|---|---|---|---|
| 1 | **SOURCES** (grey) | ✈️ / 🏠 | Public travel data | BTS flights 2019–2025 · Inside Airbnb, 20 cities · OurAirports · ECB FX |
| 2 | **LAKE** (blue) | AWS S3 bucket | Amazon S3 | `raw/<table>/<partition>/` · 1,200 gzip CSVs · 6 GB · Terraform-managed |
| 3 | **BRONZE** (brown) | Snowflake | Snowflake RAW | 10 tables · 294M rows · COPY INTO via storage integration (keyless) |
| 4 | **SILVER** (grey) | Snowflake | STAGING (dbt) | clean · type · dedupe · 10 views + 5 seeds |
| — | small label on the arrow 4→5 | dbt logo | dbt | |
| 5 | **GOLD** (amber) | Snowflake | MARTS (dbt) | 6 dims · 3 incremental facts · 5 marts · SCD2 snapshot |
| 6 | **SERVE** (red) | Streamlit · Snowflake | Streamlit dashboard | 7 pages · RAG chat · text-to-SQL · read-only role |

Under box 1, a small dashed side-box feeding box 2:
**Synthetic layer** — `generate_data.py` (DuckDB) · users = pseudonymised reviewers ·
bookings anchored on real reviews and real BTS flights.

---

## Band 2 — AI LANE · THREE CAPABILITIES (dashed blue frame)

Header line: **AI LANE – THREE CAPABILITIES** · Google Gemini · gemini-3.5-flash · gemini-3.5-flash-lite · gemini-embedding-001

Each row: number badge, title + subtitle on the left, then four boxes joined by arrows.
Dashed connector lines go up from the AI lane to SILVER, GOLD and SERVE (as in the reference).

| # | Title / subtitle | Box A | Box B (highlighted) | Box C | Box D |
|---|---|---|---|---|---|
| 1 | **LLM ENRICHMENT** — LLM as a transform step | `stg_airbnb__reviews` | `enrich_reviews.py` — 25 reviews / call · typed JSON | `AI.REVIEW_ENRICHMENTS` | `mart_review_insights` |
| 2 | **RAG** — chat with your reviews | `reviews` (22.9K indexed) | embed → 768-d vectors | **Snowflake `VECTOR`** · cosine search in SQL | `rag.py` — grounded answer · cited sources |
| 3 | **TEXT-TO-SQL** — chat with your warehouse | MARTS + AI schema (live) | `text_to_sql.py` — NL → SQL | single-SELECT guard | run as **ANALYST_ROLE** (read-only) |

Differences from the reference worth keeping visible: the vector store is *inside
Snowflake* (no FAISS / parquet), and text-to-SQL runs as a *read-only* role.

---

## Band 3 — ORCHESTRATION

Left card: Airflow logo · **Apache Airflow 3.3** · DAG `nomad_hub_daily` · Docker Compose

Then four task-group boxes with arrows (the DAG's real task groups):

| Box | Title | Subtitle |
|---|---|---|
| 1 | `ingest` | COPY INTO · S3 → RAW (new files only) |
| 2 | `transform` | dbt deps → dbt build · RAW → STAGING → MARTS + tests |
| 3 | `ai.enrich_reviews` → `ai.embed_reviews` | Gemini enrichment + RAG index (incremental) |
| 4 | `ai.dbt_build_ai` | AI marts |

Small dashed arrows up from each box to the AI lane / pipeline, as in the reference.

---

## Band 4 — FOUNDATION & TOOLS (one row of logos)

Python · DuckDB · **Terraform** · AWS S3 · Snowflake · dbt · Google Gemini · Airflow · Streamlit · Docker

Right-hand security block (padlock icon):
**Security** — keyless S3 trust (IAM role + external ID) · key-pair service users ·
least-privilege roles (LOADER / DBT / ANALYST) · resource monitor credit cap

---

## Colour hints

Keep the reference's header colours for the medallion layers (Bronze brown, Silver grey,
Gold amber), blue for the lake, red for serve, and a dashed blue frame for the AI lane.
Use one accent (blue) for highlighted AI boxes so the diagram stays calm.
