# NomadHub AI Data Platform — Architecture & Conventions

Bu doküman, **NomadHub AI Data Platform** projesinin mimarisini, veri modelini, teknoloji yığınını ve geliştirme standartlarını özetler.

---

## 1. Proje Özeti
- **Domain**: Dijital Göçebe & Seyahat Veri Platformu (Uçuşlar, Oteller, Yorumlar, Kullanıcı Kohortları).
- **Proje Adı**: NomadHub AI Data Platform

---

## 2. Mimari Katmanları & Teknoloji Yığını

### 1. Sentetik Veri Üretimi (`/data`)
- `generate_data.py`: Faker tabanlı, ilişkisel bütünlüğe sahip 7 tablo üretir:
  - `countries`, `airports`, `hotels`, `users`, `flights`, `hotel_bookings`, `reviews`

### 2. Bulut Depolama (`/aws`)
- S3 Bucket: `s3://nomadhub-data-platform/` (Raw/Bronze katmanı).
- `upload_to_s3.py`: Üretilen CSV'leri klasör bazlı S3'e yükler.

### 3. Data Warehouse — Medallion Mimarisi (`/snowflake`)
- **RAW (Bronze)**: S3 external stage üzerinden `COPY INTO` ile yüklenen ham tablolar.
- **STAGING (Silver)**: dbt view modelleri ile veri temizleme ve standardizasyon.
- **MARTS (Gold)**: Star schema (Fact & Dimension) + İş zekası metrik modelleri.
- **AI**: Gemini 1.5 Flash ile zenginleştirilmiş `REVIEW_ENRICHED` tablosu.

### 4. Veri Dönüşümü (`/nomad_hub`)
- **dbt-core & dbt-snowflake**:
  - Şema yönetimi için `macros/generate_schema_name.sql`.
  - Etiketleme (`dimension`, `fact`, `gold`).
  - Veri kalitesi testleri (`schema.yml`).

### 5. Orkestrasyon (`/airflow`)
- `nomad_pipeline.py`: 4 adet `TaskGroup` içeren Airflow DAG:
  1. `ingest`: S3 -> Snowflake RAW paralel `COPY INTO` + doğrulama.
  2. `transform`: dbt staging -> dims/facts -> business marts -> test.
  3. `ai_enrich`: Gemini ile yorum analizi + doğrulama.
  4. `ai_marts`: AI mart modelleri + genel testler.

### 6. Yapay Zeka Katmanı (`/ai`)
- `enrich_reviews.py`: Google Gemini 1.5 Flash ile duygu, duygu durumu (emotion), kategori ve toksisite analizi.
- `rag_service.py`: Seyahat & platform bilgisi için RAG servisi.
- `text_to_sql.py`: Doğal dilden Snowflake SQL sorgusu üreten LLM asistanı.

### 7. Dashboard & UI (`/streamlit`)
- 6 sayfalı zengin Plotly & Streamlit arayüzü (`app.py`):
  - 📍 Overview KPIs & Trendler
  - ✈️ Flight Analytics
  - 🏨 Hotel Analytics
  - 🧠 AI Review Insights
  - 💬 RAG Chat
  - 🔍 SQL Assistant

### 8. CI/CD (`/.github/workflows`)
- `dbt_ci.yml`: Pull request ve push işlemlerinde dbt compile, test ve Python ruff lint doğrulamaları.

---

## 3. Geliştirme ve Güvenlik Kuralları
- Hassas anahtarlar (Snowflake şifresi, AWS keys, Gemini API key) `.env` dosyalarında tutulmalı, depoya `.env.example` yüklenmelidir.
- Yeni modeller eklenirken `generate_schema_name` makrosunun kurallarına uyulmalıdır.
