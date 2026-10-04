"""
Inside Airbnb — listings, calendar, reviews for 20 cities
=========================================================
Real short-term-rental data scraped from Airbnb: listing attributes & prices,
365-day forward availability calendar, and every public review (free text, many languages).

Source : https://insideairbnb.com/get-the-data/   (CC BY 4.0 — attribution required)
Output : raw/listings/city=<city>/listings_<city>_<snapshot>.csv.gz
         raw/calendar/city=<city>/calendar_<city>_<snapshot>.csv.gz
         raw/reviews/city=<city>/reviews_<city>_<snapshot>.csv.gz

Notes
- Only the latest snapshot per city is public; its date is discovered from the
  get-the-data page. A later re-run picks up newer snapshots as new files.
- Each snapshot's reviews file contains the city's full review history, so review_id
  is unique per snapshot but repeats across snapshots — dbt staging dedupes.
- Personal data is dropped at download: host/reviewer names, profile & picture URLs,
  host "about" text.
- The calendar no longer carries prices; price lives on the listing (local currency).
"""

import re
from pathlib import Path

import requests

from .common import CACHE_DIR, HEADERS, RAW_DIR, csv_to_gzip, download, rel

PAGE_URL = "https://insideairbnb.com/get-the-data/"
LICENSE = "CC BY 4.0 — Inside Airbnb (insideairbnb.com)"

# city key -> (country slug, city slug) as they appear in data.insideairbnb.com URLs
CITIES = {
    # United States — linkable to real BTS flights into the same metro
    "new_york":      ("united-states", "new-york-city"),
    "los_angeles":   ("united-states", "los-angeles"),
    "san_francisco": ("united-states", "san-francisco"),
    "chicago":       ("united-states", "chicago"),
    "seattle":       ("united-states", "seattle"),
    "boston":        ("united-states", "boston"),
    "austin":        ("united-states", "austin"),
    "washington_dc": ("united-states", "washington-dc"),
    "new_orleans":   ("united-states", "new-orleans"),
    "hawaii":        ("united-states", "hawaii"),
    # International
    "london":        ("united-kingdom", "london"),
    "paris":         ("france", "paris"),
    "istanbul":      ("turkey", "istanbul"),
    "barcelona":     ("spain", "barcelona"),
    "madrid":        ("spain", "madrid"),
    "amsterdam":     ("the-netherlands", "amsterdam"),
    "munich":        ("germany", "munich"),
    "rome":          ("italy", "rome"),
    "lisbon":        ("portugal", "lisbon"),
    "tokyo":         ("japan", "tokyo"),
}

LISTING_COLUMNS = {c: c for c in [
    "id", "last_scraped", "name", "description",
    "host_id", "host_since", "host_response_rate", "host_acceptance_rate",
    "host_is_superhost", "calculated_host_listings_count",
    "neighbourhood_cleansed", "neighbourhood_group_cleansed", "latitude", "longitude",
    "property_type", "room_type", "accommodates", "bathrooms", "bathrooms_text",
    "bedrooms", "beds", "amenities", "price", "minimum_nights", "maximum_nights",
    "has_availability", "availability_30", "availability_90", "availability_365",
    "number_of_reviews", "number_of_reviews_ltm", "first_review", "last_review",
    "review_scores_rating", "review_scores_accuracy", "review_scores_cleanliness",
    "review_scores_checkin", "review_scores_communication", "review_scores_location",
    "review_scores_value", "instant_bookable", "license",
    "estimated_occupancy_l365d", "estimated_revenue_l365d",
]}
LISTING_COLUMNS["id"] = "listing_id"

CALENDAR_COLUMNS = {
    "listing_id": "listing_id",
    "date": "calendar_date",
    "available": "available",
    "minimum_nights": "minimum_nights",
    "maximum_nights": "maximum_nights",
}

REVIEW_COLUMNS = {           # reviewer_name intentionally excluded (PII)
    "id": "review_id",
    "listing_id": "listing_id",
    "date": "review_date",
    "reviewer_id": "reviewer_id",
    "comments": "comments",
}

FILES = {"listings": LISTING_COLUMNS, "calendar": CALENDAR_COLUMNS, "reviews": REVIEW_COLUMNS}


def discover_snapshots(cities: list[str]) -> dict[str, tuple[str, str]]:
    """Return {city: (base_url, snapshot_date)} for the latest snapshot of each city."""
    resp = requests.get(PAGE_URL, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    # The page sends no charset header, so requests would guess Latin-1 and mangle
    # non-ASCII URL segments (e.g. japan/kantō/tokyo). It is UTF-8.
    html = resp.content.decode("utf-8")
    found = {}
    for city in cities:
        country, slug = CITIES[city]
        pattern = (
            rf"(https://data\.insideairbnb\.com/{re.escape(country)}/[^/\"]+/{re.escape(slug)}/"
            rf"(\d{{4}}-\d{{2}}-\d{{2}}))/data/listings\.csv\.gz"
        )
        matches = re.findall(pattern, html)
        if not matches:
            raise RuntimeError(f"No Inside Airbnb snapshot found for {city} ({country}/{slug})")
        base, snapshot = max(matches, key=lambda m: m[1])
        found[city] = (base, snapshot)
    return found


def output_path(table: str, city: str, snapshot: str) -> Path:
    return RAW_DIR / table / f"city={city}" / f"{table}_{city}_{snapshot}.csv.gz"


def fetch_city(city: str, base_url: str, snapshot: str, keep_cache: bool = False) -> list[dict]:
    """Download listings/calendar/reviews for one city snapshot. Idempotent per file."""
    results = []
    for table, columns in FILES.items():
        out = output_path(table, city, snapshot)
        url = f"{base_url}/data/{table}.csv.gz"
        if out.exists():
            results.append({"path": rel(out), "status": "cached"})
            continue

        src = download(url, CACHE_DIR / "airbnb" / city / snapshot / f"{table}.csv.gz")
        rows = csv_to_gzip(src, out, columns=columns, extra={"city": city, "snapshot_date": snapshot})
        if not keep_cache:
            src.unlink()

        results.append({
            "path": rel(out),
            "status": "downloaded",
            "source": "inside_airbnb",
            "table": table,
            "city": city,
            "snapshot_date": snapshot,
            "url": url,
            "rows": rows,
            "bytes": out.stat().st_size,
            "license": LICENSE,
        })
    return results
