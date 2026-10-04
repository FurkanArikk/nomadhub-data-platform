"""
NomadHub — Synthetic Booking Layer
===================================
Public data gives us real flights (BTS), real listings and real reviews (Inside Airbnb),
but no platform ever publishes its customers or their bookings. This script generates
exactly that missing layer — anchored on the real events, never free-floating:

  users            one per real Airbnb reviewer active 2019–2025 (pseudonymised: fake
                   name/email/birth date/home, real travel pattern). ~12.6M
  stay_bookings    every real review = one completed stay at that listing, checking out
                   just before the review date; plus cancelled bookings (no review). ~18M
  flight_bookings  US-based users flying to a US-city stay are put on a REAL BTS flight
                   from their home airport into the listing's metro (and back). If BTS
                   says that flight was cancelled, so is the booking.

Everything runs in DuckDB straight from data/raw/*.csv.gz and is written back to
data/raw/<table>/year=YYYY/month=MM/ in the same layout as the downloaded sources.
Randomness is hash-based (hash of a row key + salt), so output is identical across runs
and thread counts.

Usage:
    python data/generate_data.py                                  # all cities, 2019–2025
    python data/generate_data.py --sample                         # boston + munich, 2024–2025
    python data/generate_data.py --cities paris tokyo --start 2023-01-01
"""

import argparse
import time
import unicodedata
from pathlib import Path

import duckdb
import pandas as pd
from faker import Faker
from sources.common import rel, update_manifest

DATA_DIR = Path(__file__).resolve().parent
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / ".cache"
SEEDS_DIR = DATA_DIR.parent / "nomad_hub" / "seeds"
DB_PATH = CACHE_DIR / "generator.duckdb"

SEED = 42
NAME_POOL_SIZE = 1500
PRICE_SNAPSHOT_DATE = "2026-06-15"   # Inside Airbnb prices are "today's" prices

# ── Home markets for non-US users: country -> (Faker locale, weight) ──────────
MARKETS = {
    "GB": ("en_GB", 14), "DE": ("de_DE", 12), "FR": ("fr_FR", 11), "ES": ("es_ES", 8),
    "IT": ("it_IT", 8), "CA": ("en_CA", 8), "AU": ("en_AU", 5), "NL": ("nl_NL", 4),
    "JP": ("ja_JP", 4), "BR": ("pt_BR", 4), "TR": ("tr_TR", 3), "MX": ("es_MX", 3),
    "IN": ("en_IN", 3), "CN": ("zh_CN", 3), "PT": ("pt_PT", 2), "IE": ("en_IE", 2),
    "CH": ("de_CH", 2), "SE": ("sv_SE", 2), "BE": ("nl_BE", 2),
}
US_LOCALE = "en_US"

# Nominal yearly growth of listing prices, used to deflate 2026 prices to the stay year.
PRICE_GROWTH = {"TRY": 0.45, "JPY": 0.03}
DEFAULT_PRICE_GROWTH = 0.05

PAYMENT_METHODS = {"credit_card": 60, "paypal": 12, "apple_pay": 11, "debit_card": 9,
                   "google_pay": 6, "bank_transfer": 2}
BOOKING_CHANNELS = {"ios": 38, "web": 35, "android": 27}
ACQUISITION_CHANNELS = {"organic_search": 30, "direct": 18, "paid_search": 18,
                        "social": 16, "referral": 12, "email": 6}
EMAIL_DOMAINS = {"gmail.com": 50, "outlook.com": 14, "icloud.com": 12, "yahoo.com": 10,
                 "hotmail.com": 9, "proton.me": 5}
CABINS = {"economy": 84, "premium_economy": 8, "business": 6.5, "first": 1.5}
CABIN_MULTIPLIER = {"economy": 1.0, "premium_economy": 1.7, "business": 3.4, "first": 5.5}

CANCELLED_SHARE = 0.075      # extra cancelled bookings, relative to completed stays
FLY_SHARE = 0.85             # US-based travellers who fly (vs drive) to a US stay
HOME_AIRPORTS = 60           # US users live near one of the busiest N BTS origins


# ─────────────────────────────────────────────────────────────────────────────
# SQL helpers
# ─────────────────────────────────────────────────────────────────────────────

def weighted(u_expr: str, options: dict) -> str:
    """SQL CASE that maps a uniform [0,1) expression onto weighted string options."""
    total = sum(options.values())
    items = list(options.items())
    cum, whens = 0.0, []
    for value, weight in items[:-1]:
        cum += weight / total
        whens.append(f"WHEN {u_expr} < {cum:.6f} THEN '{value}'")
    return f"CASE {' '.join(whens)} ELSE '{items[-1][0]}' END"


def cities_sql(cities: list[str]) -> str:
    return "(" + ", ".join(f"'{c}'" for c in cities) + ")"


def city_files(table: str, cities: list[str]) -> str:
    files = [p.as_posix() for c in cities for p in sorted((RAW_DIR / table / f"city={c}").glob("*.csv.gz"))]
    if not files:
        raise SystemExit(f"No raw {table} files for {cities} — run data/download_sources.py first")
    return "[" + ", ".join(f"'{f}'" for f in files) + "]"


def step(title: str):
    print(f"\n▶ {title}")
    return time.time()


def done(con, t0: float, table: str) -> None:
    n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    print(f"  ✓ {table}: {n:,} rows ({time.time() - t0:.0f}s)")


# ─────────────────────────────────────────────────────────────────────────────
# Name pools (Faker is slow per row; we draw 1.5K names per locale once and
# assign them to millions of users by hash inside DuckDB)
# ─────────────────────────────────────────────────────────────────────────────

ASCII_MAP = str.maketrans({"ı": "i", "ł": "l", "ø": "o", "æ": "ae", "ß": "ss", "đ": "d", "œ": "oe"})


def to_ascii(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name.lower().translate(ASCII_MAP))
    cleaned = "".join(ch for ch in folded if "a" <= ch <= "z")
    return cleaned or "traveler"


def first_call(fake: Faker, *methods: str) -> str:
    for method in methods:
        if hasattr(fake, method):
            return getattr(fake, method)()
    raise AttributeError(methods)


def load_name_pools(con) -> None:
    locales = [US_LOCALE] + [loc for loc, _ in MARKETS.values()]
    first_rows, last_rows = [], []
    for locale in locales:
        fake = Faker(locale)
        fake.seed_instance(SEED)
        romanize = locale in ("ja_JP", "zh_CN")   # keep emails & display names in Latin script
        for gender in ("F", "M"):
            g = "female" if gender == "F" else "male"
            for i in range(NAME_POOL_SIZE):
                if romanize:
                    first = first_call(fake, f"first_romanized_name_{g}", "first_romanized_name")
                else:
                    first = first_call(fake, f"first_name_{g}")
                first_rows.append((locale, gender, i, first, to_ascii(first)))
        for i in range(NAME_POOL_SIZE):
            last = first_call(fake, "last_romanized_name", "last_name") if romanize else fake.last_name()
            last_rows.append((locale, i, last, to_ascii(last)))

    # Bulk-load via DataFrames — row-by-row executemany is very slow in DuckDB.
    first_df = pd.DataFrame(first_rows, columns=["locale", "gender", "idx", "name", "ascii"])
    last_df = pd.DataFrame(last_rows, columns=["locale", "idx", "name", "ascii"])
    markets_df = pd.DataFrame(
        [("US", US_LOCALE)] + [(cc, loc) for cc, (loc, _) in MARKETS.items()],
        columns=["country_code", "locale"],
    )
    for table, df in (("first_names", first_df), ("last_names", last_df), ("markets", markets_df)):
        con.register(f"{table}_df", df)
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM {table}_df")
        con.unregister(f"{table}_df")


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def build(con, cities: list[str], start: str, end: str) -> None:
    con.execute(f"""
        CREATE MACRO u(k, salt) AS (hash(k::VARCHAR || '|' || salt || '|{SEED}') % 1000000007) / 1000000007.0;
        CREATE MACRO z(k, salt) AS sqrt(-2 * ln(greatest(u(k, salt || 'a'), 1e-12))) * cos(2 * pi() * u(k, salt || 'b'));
        CREATE MACRO expo(k, salt, mean) AS -ln(1 - u(k, salt)) * mean;
    """)

    # ── 1. Reference + real sources ─────────────────────────────────────────
    t0 = step("Loading seeds and real sources")
    con.execute(f"""
        CREATE TABLE cities AS SELECT * FROM read_csv('{SEEDS_DIR / "cities.csv"}', header=true);
        CREATE TABLE city_airports AS SELECT * FROM read_csv('{SEEDS_DIR / "city_airports.csv"}', header=true, all_varchar=true);
    """)
    load_name_pools(con)

    con.execute(f"""
        CREATE TABLE reviews AS
        SELECT DISTINCT ON (review_id) review_id, listing_id, city, review_date, reviewer_id
        FROM (
            SELECT try_cast(review_id AS BIGINT) AS review_id, try_cast(listing_id AS BIGINT) AS listing_id,
                   city, try_cast(review_date AS DATE) AS review_date,
                   try_cast(reviewer_id AS BIGINT) AS reviewer_id, snapshot_date
            FROM read_csv({city_files("reviews", cities)}, header=true, all_varchar=true)
        )
        WHERE review_id IS NOT NULL AND reviewer_id IS NOT NULL
          AND review_date BETWEEN DATE '{start}' AND DATE '{end}'
        ORDER BY review_id, snapshot_date DESC
    """)
    done(con, t0, "reviews")

    # Listings: parse price (local currency despite the '$'), fill gaps with the
    # city/room-type median, cap outliers at p97, and map each listing to its metro.
    t0 = step("Preparing listings")
    con.execute(f"""
        CREATE TABLE listings AS
        WITH src AS (
            SELECT DISTINCT ON (listing_id) *
            FROM (
                SELECT try_cast(listing_id AS BIGINT) AS listing_id, city, snapshot_date,
                       neighbourhood_group_cleansed AS grp, room_type,
                       try_cast(accommodates AS INT) AS accommodates,
                       try_cast(minimum_nights AS INT) AS min_nights,
                       try_cast(replace(replace(price, '$', ''), ',', '') AS DOUBLE) AS price
                FROM read_csv({city_files("listings", cities)}, header=true, all_varchar=true)
            )
            WHERE listing_id IS NOT NULL
            ORDER BY listing_id, snapshot_date DESC
        ),
        stats AS (
            SELECT city, room_type, median(price) AS med, quantile_cont(price, 0.97) AS p97
            FROM src WHERE price > 0 GROUP BY ALL
        ),
        metros AS (SELECT DISTINCT city, neighbourhood_group, metro_key FROM city_airports)
        SELECT r.listing_id, r.city, r.room_type, c.currency_code, c.is_us, m.metro_key,
               greatest(coalesce(r.accommodates, 2), 1)          AS accommodates,
               least(greatest(coalesce(r.min_nights, 1), 1), 30) AS min_nights,
               least(coalesce(nullif(r.price, 0), s.med), s.p97) AS price_local
        FROM src r
        JOIN cities c USING (city)
        JOIN stats s USING (city, room_type)
        LEFT JOIN metros m
          ON m.city = r.city AND (m.neighbourhood_group IS NULL OR m.neighbourhood_group = r.grp)
    """)
    done(con, t0, "listings")

    t0 = step("Loading BTS flights into our metros")
    con.execute(f"""
        CREATE TABLE flights AS
        SELECT try_cast(f.flight_date AS DATE)       AS flight_date,
               f.reporting_airline                   AS airline_code,
               f.flight_number, f.origin, f.dest, f.crs_dep_time,
               coalesce(try_cast(f.cancelled AS DOUBLE), 0) = 1 AS is_cancelled,
               try_cast(f.distance AS DOUBLE)        AS distance,
               o.metro_key AS origin_metro, d.metro_key AS dest_metro
        FROM read_csv('{(RAW_DIR / "flights").as_posix()}/*/*/*.csv.gz', header=true, all_varchar=true) f
        LEFT JOIN city_airports o ON o.iata_code = f.origin
        LEFT JOIN city_airports d ON d.iata_code = f.dest
        WHERE (o.metro_key IS NOT NULL OR d.metro_key IS NOT NULL)
          AND try_cast(f.flight_date AS DATE) BETWEEN DATE '{start}' - 30 AND DATE '{end}' + 30
    """)
    done(con, t0, "flights")

    # ── 2. Users: one per real reviewer ─────────────────────────────────────
    t0 = step("Generating users (pseudonymised reviewers)")
    home_weights = dict(con.execute(f"""
        SELECT origin, count(*) FROM read_csv('{(RAW_DIR / "flights").as_posix()}/*/*/*.csv.gz',
                                              header=true, all_varchar=true)
        GROUP BY 1 ORDER BY 2 DESC LIMIT {HOME_AIRPORTS}
    """).fetchall())
    market_weights = {cc: w for cc, (_, w) in MARKETS.items()}

    con.execute(f"""
        CREATE TABLE users_base AS
        WITH per_reviewer AS (
            SELECT reviewer_id,
                   arg_min(r.city, r.review_date) AS first_city,
                   min(r.review_date)             AS first_stay,
                   bool_or(c.is_us)               AS any_us_stay
            FROM reviews r JOIN cities c USING (city)
            GROUP BY reviewer_id
        ),
        homed AS (
            SELECT p.*,
                   CASE
                       WHEN p.any_us_stay AND u(reviewer_id, 'home_us') < 0.80 THEN 'US'
                       WHEN NOT p.any_us_stay AND u(reviewer_id, 'home_us') < 0.08 THEN 'US'
                       WHEN NOT fc.is_us AND u(reviewer_id, 'domestic') < 0.35 THEN fc.country_code
                       ELSE {weighted("u(reviewer_id, 'market')", market_weights)}
                   END AS home_country,
                   {weighted("u(reviewer_id, 'gender')", {"F": 49, "M": 49, "X": 2})} AS gender
            FROM per_reviewer p JOIN cities fc ON fc.city = p.first_city
        )
        SELECT row_number() OVER (ORDER BY first_stay, reviewer_id) AS user_id,
               h.*,
               CASE WHEN home_country = 'US'
                    THEN {weighted("u(reviewer_id, 'home_airport')", home_weights)} END AS home_airport,
               m.locale,
               CASE WHEN gender = 'X' THEN (CASE WHEN u(reviewer_id, 'pool') < 0.5 THEN 'F' ELSE 'M' END)
                    ELSE gender END AS pool_gender
        FROM homed h JOIN markets m ON m.country_code = h.home_country
    """)
    done(con, t0, "users_base")

    # ── 3. Stay bookings ────────────────────────────────────────────────────
    t0 = step("Generating stay bookings from real reviews")
    growth_case = " ".join(f"WHEN '{cur}' THEN {g}" for cur, g in PRICE_GROWTH.items())
    con.execute(f"""
        CREATE TABLE stays_raw AS
        WITH completed AS (
            SELECT 'r' || review_id::VARCHAR AS stay_key, review_id, reviewer_id, listing_id,
                   review_date - least(floor(expo(review_id, 'review_lag', 3)), 14)::INT AS checkout_date,
                   'completed' AS booking_status
            FROM reviews
        ),
        cancelled AS (   -- a booking the same guest made and cancelled weeks before their real stay
            SELECT 'c' || review_id::VARCHAR, NULL, reviewer_id, listing_id,
                   review_date - (14 + floor(u(review_id, 'cxl_shift') * 106))::INT,
                   'cancelled'
            FROM reviews
            WHERE u(review_id, 'cancel') < {CANCELLED_SHARE}
        ),
        both_kinds AS (SELECT * FROM completed UNION ALL SELECT * FROM cancelled),
        dated AS (
            SELECT b.*, l.city, l.room_type, l.currency_code, l.is_us, l.metro_key, l.price_local, l.accommodates,
                   greatest(l.min_nights,
                            least(round(exp(ln(3.0) + 0.65 * z(stay_key, 'nights'))), 28))::INT AS nights,
                   least(greatest(round(exp(ln(24.0) + 0.95 * z(stay_key, 'lead'))), 0), 330)::INT AS lead_days
            FROM both_kinds b JOIN listings l USING (listing_id)
        ),
        priced AS (
            SELECT d.*,
                   checkout_date - nights AS checkin_date,
                   price_local
                     / pow(1 + CASE currency_code {growth_case} ELSE {DEFAULT_PRICE_GROWTH} END,
                           datediff('day', checkout_date - nights, DATE '{PRICE_SNAPSHOT_DATE}') / 365.25)
                     * CASE WHEN month(checkout_date - nights) IN (6, 7, 8) THEN 1.18
                            WHEN month(checkout_date - nights) = 12 THEN 1.10
                            WHEN month(checkout_date - nights) IN (1, 2) THEN 0.88
                            ELSE 1.0 END
                     * exp(0.08 * z(stay_key, 'rate_noise'))                          AS rate_raw
            FROM dated d
        )
        SELECT stay_key, review_id, reviewer_id, listing_id, city, metro_key, is_us, room_type,
               currency_code, booking_status, checkin_date, checkout_date, nights,
               (checkin_date - lead_days)::TIMESTAMP
                 + to_seconds(floor(u(stay_key, 'booked_sec') * 86400)::BIGINT)       AS booked_at,
               (1 + floor(u(stay_key, 'guests') * least(accommodates, 6)))::INT      AS guests,
               CASE WHEN currency_code = 'JPY' THEN round(rate_raw) ELSE round(rate_raw, 2) END AS nightly_rate,
               CASE room_type WHEN 'Entire home/apt' THEN 0.45 WHEN 'Hotel room' THEN 0.0 ELSE 0.20 END AS cleaning_ratio
        FROM priced
    """)
    con.execute(f"""
        CREATE TABLE stays AS
        WITH fees AS (
            SELECT s.*,
                   round(nightly_rate * cleaning_ratio, 2)                         AS cleaning_fee,
                   round(nightly_rate * nights, 2)                                 AS subtotal
            FROM stays_raw s
        )
        SELECT row_number() OVER (ORDER BY booked_at, stay_key)                    AS stay_booking_id,
               ub.user_id, f.*,
               round(0.142 * (subtotal + cleaning_fee), 2)                         AS service_fee,
               round(subtotal + cleaning_fee + 0.142 * (subtotal + cleaning_fee), 2) AS total_amount,
               {weighted("u(stay_key, 'payment')", PAYMENT_METHODS)}             AS payment_method,
               {weighted("u(stay_key, 'channel')", BOOKING_CHANNELS)}            AS booking_channel,
               CASE WHEN booking_status = 'cancelled'
                    THEN booked_at + to_seconds(floor(u(stay_key, 'cxl_at')
                             * greatest(date_diff('second', booked_at, checkin_date::TIMESTAMP), 3600))::BIGINT)
               END                                                                 AS cancelled_at,
               CASE WHEN booking_status = 'cancelled'
                    THEN round((subtotal + cleaning_fee + 0.142 * (subtotal + cleaning_fee))
                               * CASE WHEN u(stay_key, 'refund') < 0.7 THEN 1.0 ELSE 0.5 END, 2)
               END                                                                 AS refund_amount
        FROM fees f JOIN users_base ub USING (reviewer_id)
    """)
    done(con, t0, "stays")

    # ── 4. Flight bookings on real BTS flights ──────────────────────────────
    t0 = step("Matching US trips to real BTS flights")
    cabin_case = weighted("u(user_id, 'cabin')", CABINS)
    mult_case = " ".join(f"WHEN '{c}' THEN {m}" for c, m in CABIN_MULTIPLIER.items())
    con.execute(f"""
        CREATE TABLE leg_requests AS
        SELECT s.stay_booking_id, s.user_id, s.booking_status AS stay_status, s.booked_at, s.guests,
               leg.leg,
               CASE leg.leg WHEN 'outbound' THEN ub.home_airport END           AS want_origin,
               CASE leg.leg WHEN 'return'   THEN ub.home_airport END           AS want_dest,
               s.metro_key,
               CASE leg.leg
                   WHEN 'outbound' THEN s.checkin_date - (u(s.stay_key, 'fly_early') < 0.2)::INT
                   ELSE s.checkout_date
               END                                                            AS flight_date,
               {cabin_case}                                                   AS cabin_class
        FROM stays s
        JOIN users_base ub USING (user_id)
        CROSS JOIN (VALUES ('outbound'), ('return')) leg(leg)
        WHERE s.is_us AND ub.home_airport IS NOT NULL
          AND u(s.stay_key, 'flies') < {FLY_SHARE}
          AND ub.home_airport NOT IN (SELECT iata_code FROM city_airports WHERE metro_key = s.metro_key)
    """)
    con.execute("""
        CREATE TABLE out_candidates AS
        SELECT *, row_number() OVER (p ORDER BY crs_dep_time, airline_code, flight_number) AS rn,
               count(*) OVER p AS cnt   -- partition total (an ORDER BY here would make it a running count)
        FROM flights WHERE dest_metro IS NOT NULL
        WINDOW p AS (PARTITION BY origin, dest_metro, flight_date);

        CREATE TABLE ret_candidates AS
        SELECT *, row_number() OVER (p_ret ORDER BY crs_dep_time, airline_code, flight_number) AS rn,
               count(*) OVER p_ret AS cnt
        FROM flights WHERE origin_metro IS NOT NULL
        WINDOW p_ret AS (PARTITION BY origin_metro, dest, flight_date);
    """)
    con.execute("""
        CREATE TABLE legs AS
        WITH out_n AS (SELECT DISTINCT origin, dest_metro, flight_date, cnt FROM out_candidates),
             ret_n AS (SELECT DISTINCT origin_metro, dest, flight_date, cnt FROM ret_candidates),
             outbound AS (
                 SELECT r.*, c.airline_code, c.flight_number, c.origin, c.dest, c.crs_dep_time,
                        c.is_cancelled, c.distance
                 FROM leg_requests r
                 JOIN out_n n ON n.origin = r.want_origin AND n.dest_metro = r.metro_key AND n.flight_date = r.flight_date
                 JOIN out_candidates c
                   ON c.origin = n.origin AND c.dest_metro = n.dest_metro AND c.flight_date = n.flight_date
                  AND c.rn = 1 + floor(u(r.stay_booking_id, 'pick_out') * n.cnt)
                 WHERE r.leg = 'outbound'
             ),
             ret AS (
                 SELECT r.*, c.airline_code, c.flight_number, c.origin, c.dest, c.crs_dep_time,
                        c.is_cancelled, c.distance
                 FROM leg_requests r
                 JOIN ret_n n ON n.origin_metro = r.metro_key AND n.dest = r.want_dest AND n.flight_date = r.flight_date
                 JOIN ret_candidates c
                   ON c.origin_metro = n.origin_metro AND c.dest = n.dest AND c.flight_date = n.flight_date
                  AND c.rn = 1 + floor(u(r.stay_booking_id, 'pick_ret') * n.cnt)
                 WHERE r.leg = 'return'
             )
        SELECT * FROM outbound UNION ALL SELECT * FROM ret
    """)
    con.execute(f"""
        CREATE TABLE flight_bookings AS
        WITH b AS (
            SELECT l.*,
                   least(l.booked_at + to_seconds(floor(expo(l.stay_booking_id::VARCHAR || l.leg, 'fb_delay', 86400))::BIGINT),
                         (l.flight_date - 1)::TIMESTAMP)                       AS fb_booked_at,
                   least(l.guests, 4)                                          AS passengers
            FROM legs l
        )
        SELECT row_number() OVER (ORDER BY fb_booked_at, stay_booking_id, leg) AS flight_booking_id,
               stay_booking_id, user_id, leg, fb_booked_at AS booked_at,
               flight_date, airline_code, flight_number, origin, dest, crs_dep_time,
               cabin_class, passengers,
               round((55 + 0.11 * distance)
                     / pow(1.03, datediff('day', flight_date, DATE '{PRICE_SNAPSHOT_DATE}') / 365.25)
                     * CASE cabin_class {mult_case} END
                     * (1 + 0.6 * exp(-greatest(datediff('day', fb_booked_at::DATE, flight_date), 0) / 10.0))
                     * exp(0.18 * z(stay_booking_id::VARCHAR || leg, 'fare')), 2)        AS fare_per_passenger_usd,
               CASE WHEN is_cancelled THEN 'cancelled_by_airline'
                    WHEN stay_status = 'cancelled' THEN 'cancelled_by_customer'
                    ELSE 'flown' END                                           AS booking_status
        FROM b
    """)
    n_req, n_legs = con.execute("SELECT (SELECT count(*) FROM leg_requests), (SELECT count(*) FROM legs)").fetchone()
    print(f"  legs requested {n_req:,}, matched to a real flight {n_legs:,} ({n_legs / max(n_req, 1):.0%}); "
          "unmatched = no direct flight that day (traveller connects/drives)")
    done(con, t0, "flight_bookings")

    # ── 5. Final users (signup before first booking) ────────────────────────
    t0 = step("Finalising users")
    con.execute(f"""
        CREATE TABLE users AS
        WITH first_booking AS (SELECT user_id, min(booked_at) AS first_booked_at FROM stays GROUP BY 1)
        SELECT ub.user_id,
               ub.reviewer_id                                                   AS source_reviewer_id,
               fn.name AS first_name, ln.name AS last_name,
               fn.ascii || '.' || ln.ascii || ub.user_id::VARCHAR || '@'
                 || {weighted("u(ub.reviewer_id, 'domain')", EMAIL_DOMAINS)}    AS email,
               ub.gender,
               ub.first_stay - ((23 + least(floor(abs(z(ub.reviewer_id, 'age')) * 13), 55)) * 365
                                + floor(u(ub.reviewer_id, 'dob') * 365))::INT   AS birth_date,
               ub.home_country AS home_country_code,
               ub.home_airport,
               left(ub.locale, 2)                                               AS preferred_language,
               (fb.first_booked_at - to_seconds(floor(expo(ub.reviewer_id, 'signup', 120 * 86400))::BIGINT)) AS signed_up_at,
               {weighted("u(ub.reviewer_id, 'acq')", ACQUISITION_CHANNELS)}     AS acquisition_channel,
               u(ub.reviewer_id, 'optin') < 0.42                                AS marketing_opt_in
        FROM users_base ub
        JOIN first_booking fb USING (user_id)
        JOIN first_names fn ON fn.locale = ub.locale AND fn.gender = ub.pool_gender
                           AND fn.idx = hash(ub.reviewer_id::VARCHAR || 'fn') % {NAME_POOL_SIZE}
        JOIN last_names ln ON ln.locale = ub.locale
                          AND ln.idx = hash(ub.reviewer_id::VARCHAR || 'ln') % {NAME_POOL_SIZE}
    """)
    done(con, t0, "users")


# ─────────────────────────────────────────────────────────────────────────────
# Export
# ─────────────────────────────────────────────────────────────────────────────

EXPORTS = {
    "users": ("signed_up_at", """
        SELECT user_id, source_reviewer_id, first_name, last_name, email, gender, birth_date,
               home_country_code, home_airport, preferred_language, signed_up_at,
               acquisition_channel, marketing_opt_in
        FROM users"""),
    "stay_bookings": ("booked_at", """
        SELECT stay_booking_id, user_id, listing_id, city, review_id, booked_at,
               checkin_date, checkout_date, nights, guests, currency_code, nightly_rate,
               cleaning_fee, service_fee, total_amount, payment_method, booking_channel,
               booking_status, cancelled_at, refund_amount
        FROM stays"""),
    "flight_bookings": ("booked_at", """
        SELECT flight_booking_id, stay_booking_id, user_id, leg, booked_at, flight_date,
               airline_code, flight_number, origin, dest, crs_dep_time, cabin_class,
               passengers, fare_per_passenger_usd,
               round(fare_per_passenger_usd * passengers, 2) AS total_fare_usd,
               booking_status
        FROM flight_bookings"""),
}


def export(con) -> None:
    for table, (ts_col, select) in EXPORTS.items():
        t0 = step(f"Writing data/raw/{table}/")
        out = (RAW_DIR / table).as_posix()
        con.execute(f"""
            COPY (
                SELECT *, strftime({ts_col}, '%Y') AS year, strftime({ts_col}, '%m') AS month
                FROM ({select})
            ) TO '{out}' (
                FORMAT csv, HEADER true, COMPRESSION gzip, FILE_EXTENSION 'csv.gz',
                PARTITION_BY (year, month), OVERWRITE true, FILENAME_PATTERN '{table}_{{i}}'
            )
        """)
        files = sorted((RAW_DIR / table).glob("year=*/month=*/*.csv.gz"))
        size = sum(f.stat().st_size for f in files) / 2**30
        print(f"  ✓ {len(files)} files, {size:.2f} GB ({time.time() - t0:.0f}s)")

        counts = dict(con.execute(f"""
            SELECT 'year=' || strftime({ts_col}, '%Y') || '/month=' || strftime({ts_col}, '%m'), count(*)
            FROM ({select}) GROUP BY 1
        """).fetchall())
        entries = []
        for partition, rows in counts.items():
            part_files = sorted((RAW_DIR / table / partition).glob("*.csv.gz"))
            path = part_files[0] if len(part_files) == 1 else RAW_DIR / table / partition
            entries.append({
                "path": rel(path), "status": "generated", "source": "nomadhub_synthetic",
                "table": table, "rows": rows,
                "bytes": sum(f.stat().st_size for f in part_files),
                "license": "Synthetic (generated by data/generate_data.py on top of BTS + Inside Airbnb)",
            })
        update_manifest(entries, replace_prefix=f"{table}/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate NomadHub users & bookings on top of real data")
    parser.add_argument("--sample", action="store_true", help="boston + munich, 2024-01-01..2025-12-31")
    parser.add_argument("--cities", nargs="+", help="cities to include (default: all in cities.csv)")
    parser.add_argument("--start", default="2019-01-01", help="first review/stay date")
    parser.add_argument("--end", default="2025-12-31", help="last review/stay date")
    parser.add_argument("--threads", type=int, default=16)
    parser.add_argument("--memory-limit", default="9GB")
    args = parser.parse_args()

    all_cities = [line.split(",")[0] for line in (SEEDS_DIR / "cities.csv").read_text().splitlines()[1:]]
    cities = args.cities or (["boston", "munich"] if args.sample else all_cities)
    start, end = ("2024-01-01", "2025-12-31") if args.sample else (args.start, args.end)

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    DB_PATH.unlink(missing_ok=True)          # scratch database, rebuilt every run
    con = duckdb.connect(str(DB_PATH))
    con.execute(f"SET threads={args.threads}; SET memory_limit='{args.memory_limit}'; "
                f"SET temp_directory='{(CACHE_DIR / 'duckdb_tmp').as_posix()}'; SET preserve_insertion_order=false")

    print(f"{'=' * 64}\n  NomadHub synthetic layer — {len(cities)} cities, {start} → {end}\n{'=' * 64}")
    t_all = time.time()
    build(con, cities, start, end)
    export(con)
    con.close()
    DB_PATH.unlink(missing_ok=True)
    print(f"\n✅ Done in {(time.time() - t_all) / 60:.1f} min")


if __name__ == "__main__":
    main()
