"""
NomadHub Synthetic Data Generator
===================================
Generates realistic travel & booking datasets:
  - countries.csv       ~250 rows
  - airports.csv        ~10K rows
  - hotels.csv          ~50K rows
  - users.csv           ~1M rows
  - flights.csv         ~12M rows  (configurable)
  - hotel_bookings.csv  ~15M rows  (configurable)
  - reviews.csv         ~400K rows (configurable)

Usage:
    python generate_data.py                    # full scale
    python generate_data.py --scale small      # 1% scale for testing
    python generate_data.py --scale medium     # 10% scale
    python generate_data.py --scale full       # default
    python generate_data.py --flights 500000   # custom row count
"""

import argparse
import csv
import os
import random
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, *args, **kwargs):
        return iterable

# ── Reproducibility ────────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
fake = Faker(["en_US", "en_GB", "de_DE", "fr_FR", "es_ES", "tr_TR"])
Faker.seed(SEED)

# ── Output directory ───────────────────────────────────────────────────────────
OUT_DIR = Path(__file__).parent
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Scale presets ──────────────────────────────────────────────────────────────
SCALE_PRESETS = {
    "small": {
        "users": 5_000,
        "hotels": 500,
        "airports": 200,
        "flights": 50_000,
        "hotel_bookings": 60_000,
        "reviews": 2_000,
    },
    "medium": {
        "users": 100_000,
        "hotels": 5_000,
        "airports": 1_000,
        "flights": 1_200_000,
        "hotel_bookings": 1_500_000,
        "reviews": 40_000,
    },
    "full": {
        "users": 1_000_000,
        "hotels": 50_000,
        "airports": 10_000,
        "flights": 12_000_000,
        "hotel_bookings": 15_000_000,
        "reviews": 400_000,
    },
}

# ── Reference data ─────────────────────────────────────────────────────────────
COUNTRIES = [
    ("TR", "Turkey", "Europe"),
    ("US", "United States", "North America"),
    ("GB", "United Kingdom", "Europe"),
    ("DE", "Germany", "Europe"),
    ("FR", "France", "Europe"),
    ("ES", "Spain", "Europe"),
    ("IT", "Italy", "Europe"),
    ("NL", "Netherlands", "Europe"),
    ("AE", "United Arab Emirates", "Middle East"),
    ("JP", "Japan", "Asia"),
    ("TH", "Thailand", "Asia"),
    ("SG", "Singapore", "Asia"),
    ("AU", "Australia", "Oceania"),
    ("BR", "Brazil", "South America"),
    ("MX", "Mexico", "North America"),
    ("IN", "India", "Asia"),
    ("CN", "China", "Asia"),
    ("ZA", "South Africa", "Africa"),
    ("GR", "Greece", "Europe"),
    ("PT", "Portugal", "Europe"),
    ("AT", "Austria", "Europe"),
    ("CH", "Switzerland", "Europe"),
    ("PL", "Poland", "Europe"),
    ("CZ", "Czech Republic", "Europe"),
    ("HU", "Hungary", "Europe"),
    ("RO", "Romania", "Europe"),
    ("HR", "Croatia", "Europe"),
    ("BA", "Bosnia and Herzegovina", "Europe"),
    ("RS", "Serbia", "Europe"),
    ("MK", "North Macedonia", "Europe"),
    ("AL", "Albania", "Europe"),
    ("ME", "Montenegro", "Europe"),
    ("EG", "Egypt", "Africa"),
    ("MA", "Morocco", "Africa"),
    ("TN", "Tunisia", "Africa"),
    ("KE", "Kenya", "Africa"),
    ("NG", "Nigeria", "Africa"),
    ("GH", "Ghana", "Africa"),
    ("CA", "Canada", "North America"),
    ("AR", "Argentina", "South America"),
    ("CL", "Chile", "South America"),
    ("CO", "Colombia", "South America"),
    ("PE", "Peru", "South America"),
    ("MY", "Malaysia", "Asia"),
    ("ID", "Indonesia", "Asia"),
    ("VN", "Vietnam", "Asia"),
    ("KR", "South Korea", "Asia"),
    ("PH", "Philippines", "Asia"),
    ("NZ", "New Zealand", "Oceania"),
    ("MV", "Maldives", "Asia"),
]

CABIN_CLASSES = ["Economy", "Premium Economy", "Business", "First"]
CABIN_WEIGHTS = [0.72, 0.12, 0.13, 0.03]

HOTEL_CATEGORIES = ["Budget", "Economy", "Midscale", "Upscale", "Luxury", "Ultra-Luxury"]
HOTEL_CAT_WEIGHTS = [0.20, 0.25, 0.25, 0.15, 0.12, 0.03]

BOOKING_STATUSES = ["confirmed", "cancelled", "completed", "no_show"]
BOOKING_STATUS_WEIGHTS = [0.15, 0.12, 0.68, 0.05]

PAYMENT_METHODS = ["credit_card", "debit_card", "bank_transfer", "digital_wallet", "crypto"]
PAYMENT_WEIGHTS = [0.48, 0.22, 0.12, 0.16, 0.02]

TRAVEL_PURPOSES = ["leisure", "business", "family", "honeymoon", "adventure", "medical"]
PURPOSE_WEIGHTS = [0.45, 0.28, 0.14, 0.06, 0.05, 0.02]

REVIEW_TEMPLATES = {
    "positive": [
        "Absolutely loved my trip to {dest}! The {service} was exceptional and staff were incredibly helpful.",
        "One of the best experiences I've had. {service} exceeded all expectations.",
        "Fantastic value for money! {dest} is a beautiful destination, highly recommend.",
        "Everything was perfect — from check-in to check-out. Will definitely return to {dest}.",
        "The {service} was outstanding. Clean, comfortable, and the location in {dest} is unbeatable.",
        "Amazing stay in {dest}! The facilities were top-notch and breakfast was delicious.",
        "Great experience overall. The team at {service} went above and beyond to make us comfortable.",
        "Brilliant trip! {dest} is a hidden gem. The accommodation was spotless and service impeccable.",
    ],
    "neutral": [
        "Decent stay in {dest}. {service} was okay but nothing extraordinary.",
        "Average experience. The room was clean but smaller than expected. {dest} itself was nice.",
        "It was fine. {service} is a good option if you're on a budget. Nothing to complain about really.",
        "Mixed feelings. Some aspects of {service} were great, others not so much. {dest} is worth visiting.",
        "Standard experience in {dest}. Exactly what you'd expect for the price.",
        "The trip to {dest} was decent. {service} has potential but needs improvement in a few areas.",
    ],
    "negative": [
        "Disappointed with my stay. {service} in {dest} was noisy and the customer service was poor.",
        "Would not recommend. The {service} was not as advertised — very different from photos.",
        "Very average. {dest} was nice but {service} was below standard. Overpriced for what you get.",
        "Issues with booking at {service}. Staff were unhelpful and the facilities were outdated.",
        "Not worth the price at {dest}. Had to change rooms twice and the wifi never worked.",
        "Frustrating experience. {service} in {dest} needs serious upgrades to justify the cost.",
    ],
}

AIRLINE_NAMES = [
    "SkyWing Airlines", "AirNomad", "BlueSky Express", "TravelJet",
    "NomadAir", "CloudHopper", "SwiftWings", "PureAir", "GlobalFly",
    "ZephyrAir", "HorizonJet", "TerraFly", "AeroPath", "WindRider",
]

AIRPORT_CITY_MAP = {
    "TR": [("IST", "Istanbul"), ("ESB", "Ankara"), ("AYT", "Antalya"), ("ADB", "Izmir"), ("SAW", "Istanbul Sabiha")],
    "US": [("JFK", "New York"), ("LAX", "Los Angeles"), ("ORD", "Chicago"), ("MIA", "Miami"), ("SFO", "San Francisco"), ("DFW", "Dallas"), ("SEA", "Seattle")],
    "GB": [("LHR", "London Heathrow"), ("LGW", "London Gatwick"), ("MAN", "Manchester"), ("EDI", "Edinburgh")],
    "DE": [("FRA", "Frankfurt"), ("MUC", "Munich"), ("BER", "Berlin"), ("DUS", "Dusseldorf")],
    "FR": [("CDG", "Paris Charles de Gaulle"), ("ORY", "Paris Orly"), ("NCE", "Nice"), ("LYS", "Lyon")],
    "ES": [("MAD", "Madrid"), ("BCN", "Barcelona"), ("AGP", "Malaga"), ("PMI", "Palma")],
    "IT": [("FCO", "Rome Fiumicino"), ("MXP", "Milan Malpensa"), ("VCE", "Venice"), ("NAP", "Naples")],
    "AE": [("DXB", "Dubai"), ("AUH", "Abu Dhabi"), ("SHJ", "Sharjah")],
    "JP": [("NRT", "Tokyo Narita"), ("HND", "Tokyo Haneda"), ("KIX", "Osaka")],
    "TH": [("BKK", "Bangkok Suvarnabhumi"), ("DMK", "Bangkok Don Mueang"), ("HKT", "Phuket")],
    "SG": [("SIN", "Singapore Changi")],
    "AU": [("SYD", "Sydney"), ("MEL", "Melbourne"), ("BNE", "Brisbane"), ("PER", "Perth")],
    "IN": [("DEL", "Delhi"), ("BOM", "Mumbai"), ("BLR", "Bangalore"), ("MAA", "Chennai")],
    "CN": [("PEK", "Beijing Capital"), ("PVG", "Shanghai Pudong"), ("CAN", "Guangzhou")],
    "GR": [("ATH", "Athens"), ("HER", "Heraklion"), ("SKG", "Thessaloniki")],
    "PT": [("LIS", "Lisbon"), ("OPO", "Porto"), ("FAO", "Faro")],
    "NL": [("AMS", "Amsterdam Schiphol")],
    "CH": [("ZRH", "Zurich"), ("GVA", "Geneva")],
    "MV": [("MLE", "Male")],
    "EG": [("CAI", "Cairo"), ("HRG", "Hurghada"), ("SSH", "Sharm El Sheikh")],
    "MA": [("CMN", "Casablanca"), ("RAK", "Marrakech")],
    "CA": [("YYZ", "Toronto"), ("YVR", "Vancouver"), ("YUL", "Montreal")],
    "BR": [("GRU", "Sao Paulo"), ("GIG", "Rio de Janeiro")],
    "ZA": [("JNB", "Johannesburg"), ("CPT", "Cape Town")],
    "MY": [("KUL", "Kuala Lumpur")],
    "ID": [("CGK", "Jakarta"), ("DPS", "Bali")],
}


# ─────────────────────────────────────────────────────────────────────────────
# Generators
# ─────────────────────────────────────────────────────────────────────────────

def generate_countries() -> pd.DataFrame:
    """Generate countries reference table."""
    print("Generating countries...")
    rows = []
    for code, name, region in COUNTRIES:
        rows.append({
            "country_code": code,
            "country_name": name,
            "region": region,
            "currency_code": fake.currency_code(),
            "language": fake.language_name(),
            "timezone": random.choice(["UTC+0", "UTC+1", "UTC+2", "UTC+3", "UTC+5:30", "UTC+8", "UTC+9", "UTC+10", "UTC-5", "UTC-3"]),
            "visa_required": random.choice([True, False]),
            "created_at": "2020-01-01",
        })
    df = pd.DataFrame(rows)
    print(f"  → {len(df):,} countries")
    return df


def generate_airports(n: int) -> pd.DataFrame:
    """Generate airport catalog with real IATA-style codes."""
    print(f"Generating airports (~{n:,})...")
    rows = []
    airport_id = 1

    # First: add all real airports from map
    for country_code, airports in AIRPORT_CITY_MAP.items():
        country_name = next((c[1] for c in COUNTRIES if c[0] == country_code), country_code)
        for iata_code, city in airports:
            rows.append({
                "airport_id": airport_id,
                "iata_code": iata_code,
                "airport_name": f"{city} International Airport",
                "city": city,
                "country_code": country_code,
                "country_name": country_name,
                "latitude": round(random.uniform(-60, 70), 4),
                "longitude": round(random.uniform(-170, 170), 4),
                "elevation_ft": random.randint(0, 8000),
                "is_international": True,
                "is_active": True,
                "created_at": "2020-01-01",
            })
            airport_id += 1

    # Fill remaining with synthetic airports
    used_codes = {r["iata_code"] for r in rows}
    all_country_codes = [c[0] for c in COUNTRIES]
    while len(rows) < n:
        letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        code = "".join(random.choices(letters, k=3))
        if code in used_codes:
            continue
        used_codes.add(code)
        country_code = random.choice(all_country_codes)
        country_name = next((c[1] for c in COUNTRIES if c[0] == country_code), country_code)
        rows.append({
            "airport_id": airport_id,
            "iata_code": code,
            "airport_name": f"{fake.city()} Airport",
            "city": fake.city(),
            "country_code": country_code,
            "country_name": country_name,
            "latitude": round(random.uniform(-60, 70), 4),
            "longitude": round(random.uniform(-170, 170), 4),
            "elevation_ft": random.randint(0, 5000),
            "is_international": random.choice([True, False]),
            "is_active": random.choice([True, True, True, False]),
            "created_at": "2020-01-01",
        })
        airport_id += 1

    df = pd.DataFrame(rows)
    print(f"  → {len(df):,} airports")
    return df


def generate_hotels(n: int) -> pd.DataFrame:
    """Generate hotel profiles."""
    print(f"Generating hotels (~{n:,})...")
    all_country_codes = [c[0] for c in COUNTRIES]
    rows = []
    for i in tqdm(range(1, n + 1), desc="  hotels", unit="rows"):
        category = random.choices(HOTEL_CATEGORIES, weights=HOTEL_CAT_WEIGHTS)[0]
        star_map = {"Budget": (1, 2), "Economy": (2, 3), "Midscale": (3, 4),
                    "Upscale": (4, 5), "Luxury": (5, 5), "Ultra-Luxury": (5, 5)}
        star_min, star_max = star_map[category]
        stars = random.randint(star_min, star_max)

        base_price_map = {"Budget": (20, 60), "Economy": (60, 120), "Midscale": (120, 200),
                          "Upscale": (200, 400), "Luxury": (400, 1000), "Ultra-Luxury": (1000, 5000)}
        price_min, price_max = base_price_map[category]
        country_code = random.choice(all_country_codes)
        country_name = next((c[1] for c in COUNTRIES if c[0] == country_code), country_code)

        rows.append({
            "hotel_id": i,
            "hotel_name": f"{fake.company()} {random.choice(['Hotel', 'Resort', 'Suites', 'Inn', 'Lodge', 'Palace', 'Grand'])}",
            "category": category,
            "star_rating": stars,
            "country_code": country_code,
            "country_name": country_name,
            "city": fake.city(),
            "address": fake.address().replace("\n", ", "),
            "latitude": round(random.uniform(-60, 70), 4),
            "longitude": round(random.uniform(-170, 170), 4),
            "total_rooms": random.randint(10, 800),
            "base_price_usd": round(random.uniform(price_min, price_max), 2),
            "has_pool": random.choice([True, False]),
            "has_spa": random.choice([True, False]),
            "has_gym": random.choice([True, False]),
            "has_restaurant": random.choice([True, False]),
            "has_free_wifi": True,
            "pet_friendly": random.choice([True, False]),
            "is_active": random.choices([True, False], weights=[0.95, 0.05])[0],
            "opened_date": str(fake.date_between(start_date="-40y", end_date="today")),
            "created_at": "2020-01-01",
        })
    df = pd.DataFrame(rows)
    print(f"  → {len(df):,} hotels")
    return df


def generate_users(n: int) -> pd.DataFrame:
    """Generate user profiles."""
    print(f"Generating users (~{n:,})...")
    all_country_codes = [c[0] for c in COUNTRIES]
    chunk_size = 100_000
    chunks = []
    total_written = 0

    for chunk_start in tqdm(range(0, n, chunk_size), desc="  users", unit="chunks"):
        chunk_n = min(chunk_size, n - chunk_start)
        rows = []
        for i in range(chunk_n):
            uid = chunk_start + i + 1
            reg_date = fake.date_between(start_date="-8y", end_date="today")
            rows.append({
                "user_id": uid,
                "username": fake.user_name() + str(random.randint(1, 999)),
                "email": fake.email(),
                "first_name": fake.first_name(),
                "last_name": fake.last_name(),
                "date_of_birth": str(fake.date_of_birth(minimum_age=18, maximum_age=80)),
                "gender": random.choices(["M", "F", "Other"], weights=[0.48, 0.48, 0.04])[0],
                "country_code": random.choice(all_country_codes),
                "city": fake.city(),
                "phone": fake.phone_number(),
                "loyalty_tier": random.choices(["Bronze", "Silver", "Gold", "Platinum"], weights=[0.55, 0.28, 0.12, 0.05])[0],
                "loyalty_points": random.randint(0, 500_000),
                "preferred_cabin": random.choices(CABIN_CLASSES, weights=CABIN_WEIGHTS)[0],
                "preferred_hotel_category": random.choices(HOTEL_CATEGORIES, weights=HOTEL_CAT_WEIGHTS)[0],
                "newsletter_subscribed": random.choice([True, False]),
                "registration_date": str(reg_date),
                "last_login_date": str(fake.date_between(start_date=reg_date, end_date="today")),
                "is_active": random.choices([True, False], weights=[0.88, 0.12])[0],
                "created_at": str(reg_date),
            })
        chunks.append(pd.DataFrame(rows))
        total_written += chunk_n

    df = pd.concat(chunks, ignore_index=True)
    print(f"  → {len(df):,} users")
    return df


def generate_flights(n: int, n_airports: int, n_users: int) -> None:
    """Generate flight bookings, written in chunks directly to CSV."""
    print(f"Generating flights (~{n:,})...")
    out_path = OUT_DIR / "flights.csv"
    chunk_size = 200_000
    written = 0

    # Build airport pool from existing CSV
    airports_df = pd.read_csv(OUT_DIR / "airports.csv")
    iata_codes = airports_df["iata_code"].tolist()
    if len(iata_codes) < 2:
        print("  ⚠ Not enough airports generated.")
        return

    fieldnames = [
        "flight_id", "booking_ref", "user_id", "origin_iata", "destination_iata",
        "airline", "flight_number", "cabin_class", "outbound_date", "return_date",
        "is_round_trip", "num_passengers", "base_fare_usd", "taxes_usd",
        "total_fare_usd", "booking_date", "booking_status", "payment_method",
        "travel_purpose", "is_refundable", "checked_bags", "created_at",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for chunk_start in tqdm(range(0, n, chunk_size), desc="  flights", unit="chunks"):
            chunk_n = min(chunk_size, n - chunk_start)
            rows = []
            for i in range(chunk_n):
                fid = chunk_start + i + 1
                origin = random.choice(iata_codes)
                dest = random.choice(iata_codes)
                while dest == origin:
                    dest = random.choice(iata_codes)

                outbound = fake.date_between(start_date="-3y", end_date="+1y")
                is_round_trip = random.random() < 0.65
                return_date = None
                if is_round_trip:
                    return_date = outbound + timedelta(days=random.randint(1, 30))

                cabin = random.choices(CABIN_CLASSES, weights=CABIN_WEIGHTS)[0]
                fare_map = {"Economy": (80, 1200), "Premium Economy": (200, 2500),
                            "Business": (600, 8000), "First": (2000, 20000)}
                base = round(random.uniform(*fare_map[cabin]), 2)
                taxes = round(base * random.uniform(0.08, 0.20), 2)
                passengers = random.choices([1, 2, 3, 4, 5], weights=[0.45, 0.32, 0.13, 0.07, 0.03])[0]

                status = random.choices(BOOKING_STATUSES, weights=BOOKING_STATUS_WEIGHTS)[0]
                booking_date = outbound - timedelta(days=random.randint(1, 365))

                rows.append({
                    "flight_id": fid,
                    "booking_ref": f"NH-F{fid:010d}",
                    "user_id": random.randint(1, n_users),
                    "origin_iata": origin,
                    "destination_iata": dest,
                    "airline": random.choice(AIRLINE_NAMES),
                    "flight_number": f"{random.choice(['NH','SK','BL','SW','TJ'])}{random.randint(100,9999)}",
                    "cabin_class": cabin,
                    "outbound_date": str(outbound),
                    "return_date": str(return_date) if return_date else "",
                    "is_round_trip": is_round_trip,
                    "num_passengers": passengers,
                    "base_fare_usd": base,
                    "taxes_usd": taxes,
                    "total_fare_usd": round((base + taxes) * passengers, 2),
                    "booking_date": str(booking_date),
                    "booking_status": status,
                    "payment_method": random.choices(PAYMENT_METHODS, weights=PAYMENT_WEIGHTS)[0],
                    "travel_purpose": random.choices(TRAVEL_PURPOSES, weights=PURPOSE_WEIGHTS)[0],
                    "is_refundable": random.choice([True, False]),
                    "checked_bags": random.choices([0, 1, 2, 3], weights=[0.30, 0.45, 0.20, 0.05])[0],
                    "created_at": str(booking_date),
                })
            writer.writerows(rows)
            written += chunk_n

    print(f"  → {written:,} flights written to {out_path}")


def generate_hotel_bookings(n: int, n_hotels: int, n_users: int) -> None:
    """Generate hotel booking records."""
    print(f"Generating hotel_bookings (~{n:,})...")
    out_path = OUT_DIR / "hotel_bookings.csv"
    chunk_size = 200_000

    fieldnames = [
        "booking_id", "booking_ref", "user_id", "hotel_id", "room_type",
        "check_in_date", "check_out_date", "num_nights", "num_guests",
        "num_rooms", "rate_per_night_usd", "total_rate_usd", "taxes_usd",
        "total_amount_usd", "booking_date", "booking_status", "payment_method",
        "travel_purpose", "is_refundable", "breakfast_included",
        "airport_transfer", "special_requests", "created_at",
    ]

    room_types = ["Standard", "Deluxe", "Suite", "Executive", "Presidential"]
    room_weights = [0.40, 0.30, 0.18, 0.09, 0.03]
    special_requests_pool = [
        "", "", "", "Late check-out", "Early check-in",
        "High floor room", "Non-smoking room", "Quiet room",
        "Extra pillows", "Baby cot needed", "Honeymoon decoration",
    ]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        written = 0
        for chunk_start in tqdm(range(0, n, chunk_size), desc="  hotel_bookings", unit="chunks"):
            chunk_n = min(chunk_size, n - chunk_start)
            rows = []
            for i in range(chunk_n):
                bid = chunk_start + i + 1
                hotel_id = random.randint(1, n_hotels)
                check_in = fake.date_between(start_date="-3y", end_date="+6m")
                num_nights = random.choices(
                    [1, 2, 3, 4, 5, 6, 7, 10, 14, 21],
                    weights=[0.15, 0.20, 0.18, 0.12, 0.10, 0.08, 0.07, 0.05, 0.03, 0.02]
                )[0]
                check_out = check_in + timedelta(days=num_nights)
                rate = round(random.uniform(30, 2000), 2)
                num_rooms = random.choices([1, 2, 3, 4], weights=[0.65, 0.26, 0.07, 0.02])[0]
                num_guests = random.choices([1, 2, 3, 4, 5, 6], weights=[0.30, 0.38, 0.15, 0.10, 0.05, 0.02])[0]
                total_rate = round(rate * num_nights * num_rooms, 2)
                taxes = round(total_rate * random.uniform(0.08, 0.18), 2)
                booking_date = check_in - timedelta(days=random.randint(0, 365))
                status = random.choices(BOOKING_STATUSES, weights=BOOKING_STATUS_WEIGHTS)[0]

                rows.append({
                    "booking_id": bid,
                    "booking_ref": f"NH-H{bid:010d}",
                    "user_id": random.randint(1, n_users),
                    "hotel_id": hotel_id,
                    "room_type": random.choices(room_types, weights=room_weights)[0],
                    "check_in_date": str(check_in),
                    "check_out_date": str(check_out),
                    "num_nights": num_nights,
                    "num_guests": num_guests,
                    "num_rooms": num_rooms,
                    "rate_per_night_usd": rate,
                    "total_rate_usd": total_rate,
                    "taxes_usd": taxes,
                    "total_amount_usd": round(total_rate + taxes, 2),
                    "booking_date": str(booking_date),
                    "booking_status": status,
                    "payment_method": random.choices(PAYMENT_METHODS, weights=PAYMENT_WEIGHTS)[0],
                    "travel_purpose": random.choices(TRAVEL_PURPOSES, weights=PURPOSE_WEIGHTS)[0],
                    "is_refundable": random.choice([True, False]),
                    "breakfast_included": random.choice([True, False]),
                    "airport_transfer": random.choice([True, False]),
                    "special_requests": random.choice(special_requests_pool),
                    "created_at": str(booking_date),
                })
            writer.writerows(rows)
            written += chunk_n

    print(f"  → {written:,} hotel_bookings written to {out_path}")


def generate_reviews(n: int, n_users: int, n_airports: int, n_hotels: int) -> pd.DataFrame:
    """Generate free-text travel reviews."""
    print(f"Generating reviews (~{n:,})...")
    airports_df = pd.read_csv(OUT_DIR / "airports.csv")
    cities = airports_df["city"].tolist()

    rows = []
    sentiments = ["positive", "neutral", "negative"]
    sentiment_weights = [0.60, 0.25, 0.15]
    review_types = ["flight", "hotel", "destination"]
    type_weights = [0.40, 0.45, 0.15]

    for i in tqdm(range(1, n + 1), desc="  reviews", unit="rows"):
        sentiment = random.choices(sentiments, weights=sentiment_weights)[0]
        review_type = random.choices(review_types, weights=type_weights)[0]
        dest_city = random.choice(cities)

        service_map = {
            "flight": random.choice(AIRLINE_NAMES),
            "hotel": f"{fake.company()} Hotel",
            "destination": dest_city,
        }
        service = service_map[review_type]
        template = random.choice(REVIEW_TEMPLATES[sentiment])
        review_text = template.format(dest=dest_city, service=service)

        # Add some extra sentences for realism
        extras = [
            f" The {random.choice(['location', 'food', 'staff', 'rooms', 'amenities'])} was particularly {random.choice(['impressive', 'disappointing', 'average', 'noteworthy'])}.",
            f" I travelled with {random.choice(['my partner', 'family', 'colleagues', 'friends', 'solo'])} and we all had a {random.choice(['great', 'fine', 'mixed', 'poor'])} time.",
            f" Would {random.choice(['definitely', 'probably', 'not', 'maybe'])} book again.",
        ]
        review_text += random.choice(extras)

        review_date = fake.date_between(start_date="-3y", end_date="today")
        rows.append({
            "review_id": i,
            "user_id": random.randint(1, n_users),
            "review_type": review_type,
            "entity_id": random.randint(1, n_hotels if review_type == "hotel" else n_airports),
            "entity_name": service,
            "destination_city": dest_city,
            "rating": {
                "positive": random.randint(4, 5),
                "neutral": random.randint(3, 3),
                "negative": random.randint(1, 2),
            }[sentiment],
            "review_title": fake.sentence(nb_words=6).rstrip("."),
            "review_text": review_text,
            "helpful_votes": random.randint(0, 1200),
            "verified_booking": random.choices([True, False], weights=[0.75, 0.25])[0],
            "review_date": str(review_date),
            "language": random.choices(["en", "de", "fr", "tr", "es"], weights=[0.70, 0.08, 0.07, 0.08, 0.07])[0],
            "created_at": str(review_date),
        })

    df = pd.DataFrame(rows)
    print(f"  → {len(df):,} reviews")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def save_csv(df: pd.DataFrame, name: str) -> None:
    path = OUT_DIR / name
    df.to_csv(path, index=False)
    size_mb = path.stat().st_size / 1_048_576
    print(f"  ✓ Saved {path.name}: {len(df):,} rows, {size_mb:.1f} MB")


def main() -> None:
    parser = argparse.ArgumentParser(description="NomadHub synthetic data generator")
    parser.add_argument("--scale", choices=["small", "medium", "full"], default="full",
                        help="Preset scale (default: full)")
    parser.add_argument("--flights", type=int, help="Override flight row count")
    parser.add_argument("--bookings", type=int, help="Override hotel_bookings row count")
    parser.add_argument("--reviews", type=int, help="Override reviews row count")
    parser.add_argument("--users", type=int, help="Override users row count")
    args = parser.parse_args()

    cfg = SCALE_PRESETS[args.scale].copy()
    if args.flights:
        cfg["flights"] = args.flights
    if args.bookings:
        cfg["hotel_bookings"] = args.bookings
    if args.reviews:
        cfg["reviews"] = args.reviews
    if args.users:
        cfg["users"] = args.users

    print(f"\n{'=' * 60}")
    print(f"  NomadHub Data Generator — Scale: {args.scale.upper()}")
    print(f"{'=' * 60}")
    for k, v in cfg.items():
        print(f"  {k:<20} {v:>15,} rows")
    print(f"{'=' * 60}\n")

    # 1. Countries
    df_countries = generate_countries()
    save_csv(df_countries, "countries.csv")

    # 2. Airports
    df_airports = generate_airports(cfg["airports"])
    save_csv(df_airports, "airports.csv")

    # 3. Hotels
    df_hotels = generate_hotels(cfg["hotels"])
    save_csv(df_hotels, "hotels.csv")

    # 4. Users
    df_users = generate_users(cfg["users"])
    save_csv(df_users, "users.csv")

    # 5. Flights (streamed to CSV)
    generate_flights(cfg["flights"], cfg["airports"], cfg["users"])
    f_path = OUT_DIR / "flights.csv"
    print(f"  ✓ Saved flights.csv: {cfg['flights']:,} rows, {f_path.stat().st_size / 1_048_576:.1f} MB")

    # 6. Hotel Bookings (streamed to CSV)
    generate_hotel_bookings(cfg["hotel_bookings"], cfg["hotels"], cfg["users"])
    hb_path = OUT_DIR / "hotel_bookings.csv"
    print(f"  ✓ Saved hotel_bookings.csv: {cfg['hotel_bookings']:,} rows, {hb_path.stat().st_size / 1_048_576:.1f} MB")

    # 7. Reviews
    df_reviews = generate_reviews(cfg["reviews"], cfg["users"], cfg["airports"], cfg["hotels"])
    save_csv(df_reviews, "reviews.csv")

    print(f"\n{'=' * 60}")
    print("  ✅ All datasets generated successfully!")
    print(f"  📂 Output directory: {OUT_DIR.resolve()}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
