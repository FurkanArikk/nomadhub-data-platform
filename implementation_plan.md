# NomadHub — AI-Powered Travel Data Engineering Portfolio Project

## Proje Özeti

Zomato end-to-end data engineering projesinin mimarisini ve teknoloji yığınını koruyarak, **seyahat & rezervasyon domain**'inde tamamen özgün bir portföy projesi oluşturuyoruz. Proje adı: **NomadHub**.

**Temel Değişiklikler:**
- Domain: Yemek → Seyahat (Uçuş, Otel, Rezervasyon, İnceleme)
- Veri Boyutu: Zomato'dan biraz daha büyük (~12M rezervasyon, 50M aktivite, 400K inceleme)
- LLM: OpenAI → **Google Gemini API** (gemini-1.5-flash + text-embedding-004)
- Airflow DAG: Tek DAG → **Modüler, task-group tabanlı DAG mimarisi**
- dbt Modelleri: Orijinalden daha fazla mart tablosu ve analitik metrik
- Streamlit: Seyahat odaklı, daha zengin görselleştirme ve interaktif dashboard

---

## Mimari (Orijinalle Aynı Katman Yapısı, Farklı Domain)

```
SOURCE              LAKE          BRONZE           SILVER          GOLD           SERVE
NomadHub        →  Amazon S3  →  Snowflake RAW  →  STAGING (dbt) →  MARTS (dbt)  →  Streamlit
Dataset            raw/           COPY via         clean·type       dims·incr.       BI dashboard
                   7 CSV folders  storage int.     join·views       facts·marts      AI apps

AI LANE — THREE CAPABILITIES (Google Gemini)
1. LLM ENRICHMENT  stg_reviews → enrich_summary → AI.REVIEW_ENRICHED → mart_review_insights
2. RAG              reviews     → embed→vectors  → vector_store      → rag_chat.py
3. TEXT-TO-SQL      MARTS schema→ text_to_sql.py → SELECT-only guard  → run as DBT_ROLE

ORCHESTRATION: Apache Airflow 3 (Docker) — TaskGroup tabanlı modüler DAG
```

---

## Veri Modeli — NomadHub Domain

### Kaynak Tablolar (7 CSV)
| Tablo | Açıklama | Boyut |
|---|---|---|
| `countries` | Ülke/şehir referans verisi | ~250 satır |
| `airports` | Havalimanları | ~10K satır |
| `hotels` | Otel bilgileri | ~50K satır |
| `users` | Kullanıcı profilleri | ~1M satır |
| `flights` | Uçuş rezervasyonları (FACT) | **~12M satır** |
| `hotel_bookings` | Otel rezervasyonları (FACT) | **~15M satır** |
| `reviews` | Serbest metin yorumlar | **~400K satır** |

> **Toplam veri boyutu:** ~28M+ satır (Zomato'dan ~%20 daha fazla)
>
> **Neden bu boyut?** `flights` + `hotel_bookings` gerçek BI senaryosu için yeterli hacim sağlar. `reviews` Zomato'da 300K'yken burada 400K'ya çıkarıyoruz.

---

## User Review Required

> [!IMPORTANT]
> **Gemini API Anahtarı:** Google AI Studio'dan ücretsiz Gemini API anahtarı alman gerekecek (https://aistudio.google.com/). OpenAI yerine Gemini kullanıyoruz.
> Embedding için `text-embedding-004`, enrichment için `gemini-1.5-flash` modelleri kullanılacak.

> [!IMPORTANT]
> **AWS & Snowflake Hesapları:** Orijinal projeyle aynı — aktif bir AWS hesabı (S3 bucket) ve Snowflake trial/hesabı gerekiyor. Bu kurulumları sana adım adım göstereceğim.

> [!WARNING]
> **Veri Üretimi:** Büyük fact tabloları (`flights`: 12M, `hotel_bookings`: 15M) üretmek CPU yoğun olabilir. Data generator script'ini paralel/chunk'lı yazacağım.

---

## Proposed Changes

### Component 1: Proje İskelet & Konfigürasyon

#### [NEW] [`README.md`](file:///home/furkan/work/zomata_data_eng/README.md)
Tamamen özgün, portfolio'ya uygun açıklama. Mimari şeması, kurulum talimatları, tech stack rozeti.

#### [NEW] [`.gitignore`](file:///home/furkan/work/zomata_data_eng/.gitignore)
Python, dbt, Airflow, Streamlit için kapsamlı gitignore.

#### [NEW] [`pyproject.toml`](file:///home/furkan/work/zomata_data_eng/pyproject.toml)
Proje bağımlılıkları tek dosyada.

---

### Component 2: Data Generator (Özgün — Zomato'da yoktu bu kalitede)

#### [NEW] [`data/generate_data.py`](file:///home/furkan/work/zomata_data_eng/data/generate_data.py)
**Faker** + **Pandas** ile gerçekçi seyahat verisi üretimi:
- Havalimanı kodları (IATA), uçuş rotaları, otel kategorileri
- Realistische fiyatlandırma (sezon bazlı, rota bazlı)
- Serbest metin yorumlar (Faker + şablon tabanlı, Türkçe/İngilizce mix)
- Chunk-by-chunk büyük dosya yazımı (memory-efficient)

**Üretilecek CSV'ler:** `data/` klasörüne
```
data/
├── countries.csv
├── airports.csv  
├── hotels.csv
├── users.csv
├── flights.csv          # ~12M satır, ~800MB
├── hotel_bookings.csv   # ~15M satır, ~1.2GB
└── reviews.csv          # ~400K satır, ~80MB
```

---

### Component 3: AWS & Snowflake Kurulum

#### [NEW] [`snowflake/01_setup.sql`](file:///home/furkan/work/zomata_data_eng/snowflake/01_setup.sql)
```sql
-- Warehouse: NOMAD_WH
-- Database: NOMAD_HUB
-- Schemas: RAW, STAGING, MARTS, AI
-- Roles: NOMAD_ADMIN, DBT_ROLE, ANALYST_ROLE  ← 3 rol (orijinalde 2)
```

#### [NEW] [`snowflake/02_storage_integration.sql`](file:///home/furkan/work/zomata_data_eng/snowflake/02_storage_integration.sql)
S3 keyless storage integration + external stage tanımı.

#### [NEW] [`snowflake/03_stage_and_formats.sql`](file:///home/furkan/work/zomata_data_eng/snowflake/03_stage_and_formats.sql)
CSV file format + external stage + Parquet format (ek olarak).

#### [NEW] [`snowflake/04_raw_tables.sql`](file:///home/furkan/work/zomata_data_eng/snowflake/04_raw_tables.sql)
7 RAW tablo DDL'i — tam kolon tanımları, comment'ler dahil.

#### [NEW] [`snowflake/05_copy_into.sql`](file:///home/furkan/work/zomata_data_eng/snowflake/05_copy_into.sql)
COPY INTO komutları + load monitoring query'leri.

#### [NEW] [`snowflake/06_row_access_policies.sql`](file:///home/furkan/work/zomata_data_eng/snowflake/06_row_access_policies.sql)
**EKSTRA (orijinalde yok):** Row-level security policy örneği.

#### [NEW] [`aws/iam/s3_policy.json`](file:///home/furkan/work/zomata_data_eng/aws/iam/s3_policy.json)
Snowflake için minimum privilege S3 IAM policy.

#### [NEW] [`aws/upload_to_s3.py`](file:///home/furkan/work/zomata_data_eng/aws/upload_to_s3.py)
Progress bar'lı, paralel upload scripti (orijinalden daha iyi).

---

### Component 4: dbt Projesi — `nomad_hub/`

**Orijinalden farklar:**
- Daha fazla staging model (7 → 7, aynı sayı ama farklı tablolar)
- 3 ek mart modeli (revenue_cohort, cancellation_analysis, destination_performance)
- dbt tests genişletilmiş (custom generic tests + singular tests)
- dbt docs generate → GitHub Pages'e publish

#### dbt Staging (Silver) Models
```
nomad_hub/models/staging/
├── sources.yml                    # Source definitions + freshness tests
├── stg_countries.sql
├── stg_airports.sql
├── stg_hotels.sql
├── stg_users.sql
├── stg_flights.sql
├── stg_hotel_bookings.sql
├── stg_reviews.sql
└── staging.yml                    # Column tests + descriptions
```

#### dbt Marts (Gold) Models
```
nomad_hub/models/marts/
├── dimensions/
│   ├── dim_destinations.sql       # SCD2 Snapshot → dim
│   ├── dim_hotels.sql
│   ├── dim_users.sql
│   └── dim_date.sql               # Date spine
├── facts/
│   ├── fct_flights.sql            # INCREMENTAL (MERGE strategy)
│   └── fct_hotel_bookings.sql     # INCREMENTAL (MERGE strategy)
├── business_marts/
│   ├── mart_revenue_summary.sql   # Günlük gelir özeti
│   ├── mart_destination_perf.sql  # ✨ YENİ: Destinasyon performansı
│   ├── mart_cancellation.sql      # ✨ YENİ: İptal analizi
│   ├── mart_user_cohort.sql       # ✨ YENİ: Kullanıcı cohort analizi
│   └── mart_review_insights.sql   # AI enrichment sonuçları
└── marts.yml                      # Mart tests + descriptions
```

#### [NEW] `nomad_hub/macros/`
```
macros/
├── generate_schema_name.sql       # Custom schema routing
├── cents_to_dollars.sql           # ✨ YENİ: Para birimi macro
└── assert_positive_value.sql      # ✨ YENİ: Custom generic test
```

---

### Component 5: AI Layer (Gemini API) — `ai/`

**Orijinalden fark:** OpenAI → Google Gemini

#### [NEW] [`ai/enrich_reviews.py`](file:///home/furkan/work/zomata_data_eng/ai/enrich_reviews.py)
```python
# Gemini 1.5 Flash kullanarak her review'u zenginleştir:
# - sentiment (positive/neutral/negative)
# - category (flight_service/hotel_comfort/food/location/staff/value)
# - summary (1-2 cümle)
# - travel_type (business/leisure/family/solo)
# - score (1-5)
# Batch processing: 100 review/istek, rate limiting dahil
```

#### [NEW] [`ai/rag_chat.py`](file:///home/furkan/work/zomata_data_eng/ai/rag_chat.py)
```python
# Gemini text-embedding-004 ile review vektörleştirme
# FAISS vector store (Snowflake vector store yerine açık kaynak)
# Streamlit chat UI — "Chat with your travel reviews"
```

#### [NEW] [`ai/text_to_sql.py`](file:///home/furkan/work/zomata_data_eng/ai/text_to_sql.py)
```python
# MARTS schema bilgisi → Gemini'ye context olarak ver
# Doğal dil → SELECT-only SQL üret
# Snowflake'de çalıştır, sonucu göster
# Güvenlik: DBT_ROLE (read-only), SQL injection guard
```

#### [NEW] [`ai/example.env`](file:///home/furkan/work/zomata_data_eng/ai/example.env)
GEMINI_API_KEY + SNOWFLAKE_* değişkenleri.

---

### Component 6: Airflow — Modüler TaskGroup DAG

**Orijinalden fark:** Tek task listesi → **TaskGroup'larla organize edilmiş modüler DAG**

#### [NEW] [`airflow/dags/nomad_pipeline.py`](file:///home/furkan/work/zomata_data_eng/airflow/dags/nomad_pipeline.py)

```python
# DAG Yapısı:
# @daily schedule, 4 TaskGroup:
#
# ┌─ TaskGroup: ingest ──────────────────────────┐
# │  validate_source_files                        │
# │  upload_to_s3 (paralel: 7 tablo)              │
# │  copy_into_snowflake (paralel: 7 tablo)       │
# └───────────────────────────────────────────────┘
#         ↓
# ┌─ TaskGroup: transform ───────────────────────┐
# │  dbt_run_staging                             │
# │  dbt_test_staging                            │
# │  dbt_run_marts (dimensions → facts → biz)   │
# │  dbt_test_marts                             │
# └───────────────────────────────────────────────┘
#         ↓
# ┌─ TaskGroup: ai_enrich ───────────────────────┐
# │  enrich_new_reviews (Gemini)                 │
# │  upsert_to_review_enriched                   │
# └───────────────────────────────────────────────┘
#         ↓
# ┌─ TaskGroup: ai_marts ────────────────────────┐
# │  dbt_run_ai_marts                            │
# │  dbt_test_all                                │
# │  notify_success (Slack webhook - opsiyonel)  │
# └───────────────────────────────────────────────┘
```

#### [NEW] [`airflow/Dockerfile`](file:///home/furkan/work/zomata_data_eng/airflow/Dockerfile)
Snowflake provider + Gemini SDK + dbt-snowflake.

#### [NEW] [`airflow/docker-compose.yaml`](file:///home/furkan/work/zomata_data_eng/airflow/docker-compose.yaml)
Airflow 3 (api-server + scheduler + postgres).

#### [NEW] [`airflow/example.env`](file:///home/furkan/work/zomata_data_eng/airflow/example.env)
Tüm environment variables şablonu.

---

### Component 7: Streamlit Dashboard — `streamlit/`

**Orijinalden fark:** Çok sayfa + zengin görsel + seyahat teması

#### [NEW] [`streamlit/app.py`](file:///home/furkan/work/zomata_data_eng/streamlit/app.py)
Multi-page Streamlit uygulaması:
```
📍 Overview Dashboard  — KPI cards, harita, trend grafikleri
✈️  Flight Analytics    — rota analizi, doluluk, iptal oranları
🏨 Hotel Analytics     — occupancy, RevPAR, kategori karşılaştırma
💬 Review Intelligence — sentiment dağılımı, topic cloud, AI insights
🤖 AI Chat (RAG)       — "Chat with your reviews"
🔍 SQL Assistant        — text-to-SQL ile doğal dil sorgusu
```

---

### Component 8: GitHub Actions CI/CD (EKSTRA)

#### [NEW] [`.github/workflows/dbt_ci.yml`](file:///home/furkan/work/zomata_data_eng/.github/workflows/dbt_ci.yml)
PR'da otomatik `dbt compile` + `dbt test --select state:modified`.

---

## Proje Yapısı (Final)

```
nomad-hub-data-engineering/
├── README.md
├── .gitignore
├── pyproject.toml
├── data/
│   └── generate_data.py          # Veri üretme scripti
├── aws/
│   ├── iam/s3_policy.json
│   └── upload_to_s3.py
├── snowflake/
│   ├── 01_setup.sql
│   ├── 02_storage_integration.sql
│   ├── 03_stage_and_formats.sql
│   ├── 04_raw_tables.sql
│   ├── 05_copy_into.sql
│   └── 06_row_access_policies.sql
├── nomad_hub/                     # dbt project
│   ├── dbt_project.yml
│   ├── profiles.yml.example
│   ├── packages.yml
│   ├── models/
│   │   ├── staging/               # 7 Silver views
│   │   └── marts/                 # Dims + Facts + 5 Business Marts
│   ├── macros/
│   ├── snapshots/
│   └── tests/
├── airflow/
│   ├── Dockerfile
│   ├── docker-compose.yaml
│   ├── example.env
│   └── dags/
│       └── nomad_pipeline.py      # Modüler TaskGroup DAG
├── ai/
│   ├── enrich_reviews.py          # Gemini enrichment
│   ├── rag_chat.py                # RAG chat
│   ├── text_to_sql.py             # Text-to-SQL
│   └── example.env
├── streamlit/
│   └── app.py                     # Multi-page dashboard
└── .github/
    └── workflows/
        └── dbt_ci.yml
```

---

## Verification Plan

### Build Verification
```bash
# 1. Veri üretimi
python data/generate_data.py --rows-flights 1000 --rows-bookings 1000 --rows-reviews 100

# 2. dbt compile (Snowflake bağlantısı olmadan)
cd nomad_hub && dbt compile

# 3. Airflow DAG parse testi
docker compose -f airflow/docker-compose.yaml run --rm airflow-scheduler python -c "from dags.nomad_pipeline import dag; print(dag)"
```

### Manuel Doğrulama
- Snowflake'de RAW → STAGING → MARTS veri akışı
- Gemini API ile 10 test review enrichment
- Streamlit app localhost'ta çalışır durumda

---

## Uygulama Sırası

1. **Proje iskeleti** (README, .gitignore, pyproject.toml) — 30 dk
2. **Data generator** — 1-2 saat
3. **Snowflake SQL** (01-06) — 1 saat
4. **dbt staging modelleri** — 1-2 saat
5. **dbt marts modelleri** — 2-3 saat
6. **AI layer (Gemini)** — 1-2 saat
7. **Airflow DAG** — 1 saat
8. **Streamlit dashboard** — 2-3 saat
9. **GitHub Actions CI** — 30 dk
10. **README finalize + mimari diyagramı** — 30 dk

**Toplam tahmini süre:** ~12-16 saat (kod yazma)
