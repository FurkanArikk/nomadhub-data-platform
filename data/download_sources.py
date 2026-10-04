"""
NomadHub — Public Source Downloader
====================================
Fetches the real datasets NomadHub is built on into data/raw/, laid out exactly as
they will sit in S3 (raw/<table>/<partition>/<file>.csv.gz):

  flights     BTS On-Time Performance, one file per month      ~6.5M rows/year
  listings    Inside Airbnb, one file per city snapshot         20 cities
  calendar    Inside Airbnb 365-day availability                ~365 rows/listing
  reviews     Inside Airbnb review text (multi-language)
  airports    OurAirports (+ countries, regions)

Every step is idempotent: finished files are skipped, so an interrupted run can simply
be restarted. A manifest of sources, row counts and licenses is kept in
data/raw/_manifest.json.

Usage:
    python data/download_sources.py all --sample          # 1 BTS month + 2 cities (fast dev set)
    python data/download_sources.py all                   # full: 2019-01..2025-12, 20 cities
    python data/download_sources.py bts --start 2019-01 --end 2025-12 --workers 4
    python data/download_sources.py airbnb --cities paris istanbul tokyo
    python data/download_sources.py ourairports
"""

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed

from sources import airbnb, bts, ourairports
from sources.common import MANIFEST_PATH, update_manifest
from tqdm import tqdm

SAMPLE_MONTHS = ("2025-01", "2025-01")
SAMPLE_CITIES = ["boston", "munich"]


def run_bts(start: str, end: str, workers: int, keep_cache: bool) -> None:
    months = bts.month_range(start, end)
    print(f"\n✈️  BTS flights: {len(months)} months ({start} → {end}), {workers} workers")
    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(bts.fetch_month, y, m, keep_cache): (y, m) for y, m in months}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="  months", unit="month"):
            y, m = futures[fut]
            try:
                result = fut.result()
                update_manifest([result] if result["status"] == "downloaded" else [])
                results.append(result)
            except Exception as exc:  # keep going; a re-run retries only what's missing
                print(f"  ❌ {y}-{m:02d}: {exc}")
    report(results)


def run_airbnb(cities: list[str], workers: int, keep_cache: bool) -> None:
    print(f"\n🏠 Inside Airbnb: {len(cities)} cities, {workers} workers")
    snapshots = airbnb.discover_snapshots(cities)
    for city, (_, snapshot) in snapshots.items():
        print(f"  {city:<14} snapshot {snapshot}")

    results = []
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(airbnb.fetch_city, city, base, snapshot, keep_cache): city
            for city, (base, snapshot) in snapshots.items()
        }
        for fut in tqdm(as_completed(futures), total=len(futures), desc="  cities", unit="city"):
            try:
                city_results = fut.result()
                update_manifest([r for r in city_results if r["status"] == "downloaded"])
                results.extend(city_results)
            except Exception as exc:
                print(f"  ❌ {futures[fut]}: {exc}")
    report(results)


def run_ourairports() -> None:
    print("\n🛫 OurAirports: airports, countries, regions")
    results = ourairports.fetch_all()
    update_manifest(results)
    report(results)


def report(results: list[dict]) -> None:
    new = [r for r in results if r["status"] == "downloaded"]
    cached = len(results) - len(new)
    for r in sorted(new, key=lambda r: r["path"]):
        print(f"  ✅ {r['path']:<60} {r['rows']:>12,} rows  {r['bytes'] / 1_048_576:>8.1f} MB")
    if cached:
        print(f"  ⏭  {cached} file(s) already present, skipped")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download NomadHub public source data")
    parser.add_argument("source", choices=["all", "bts", "airbnb", "ourairports"])
    parser.add_argument("--sample", action="store_true",
                        help=f"small dev set: BTS {SAMPLE_MONTHS[0]} + cities {SAMPLE_CITIES}")
    parser.add_argument("--start", default="2019-01", help="first BTS month (YYYY-MM)")
    parser.add_argument("--end", default="2025-12", help="last BTS month (YYYY-MM)")
    parser.add_argument("--cities", nargs="+", choices=sorted(airbnb.CITIES),
                        help="Inside Airbnb cities (default: all 20)")
    parser.add_argument("--workers", type=int, default=4, help="parallel downloads (default: 4)")
    parser.add_argument("--keep-cache", action="store_true",
                        help="keep original downloads in data/.cache")
    args = parser.parse_args()

    start, end = SAMPLE_MONTHS if args.sample else (args.start, args.end)
    cities = args.cities or (SAMPLE_CITIES if args.sample else list(airbnb.CITIES))

    if args.source in ("all", "ourairports"):
        run_ourairports()
    if args.source in ("all", "airbnb"):
        run_airbnb(cities, args.workers, args.keep_cache)
    if args.source in ("all", "bts"):
        run_bts(start, end, args.workers, args.keep_cache)

    print(f"\n📒 Manifest: {MANIFEST_PATH}")
    print("   Next: upload data/raw/ to s3://<bucket>/raw/ (same layout)\n")


if __name__ == "__main__":
    main()
