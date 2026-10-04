"""
OurAirports — airports, countries, regions
===========================================
~86K airports worldwide with real coordinates, IATA/ICAO codes and scheduled-service flag;
ISO countries and first-level regions (US states etc.).

Source : https://ourairports.com/data/   (public domain)
Output : raw/airports/airports.csv.gz, raw/countries/countries.csv.gz, raw/regions/regions.csv.gz

Small reference files — re-downloaded (overwritten) on every run to stay current.
"""

from .common import CACHE_DIR, RAW_DIR, csv_to_gzip, download, rel

URL = "https://davidmegginson.github.io/ourairports-data/{name}.csv"
LICENSE = "Public domain (OurAirports)"
TABLES = ["airports", "countries", "regions"]


def fetch_all() -> list[dict]:
    results = []
    for table in TABLES:
        url = URL.format(name=table)
        cache = CACHE_DIR / "ourairports" / f"{table}.csv"
        cache.unlink(missing_ok=True)
        download(url, cache)

        out = RAW_DIR / table / f"{table}.csv.gz"
        out.unlink(missing_ok=True)
        rows = csv_to_gzip(cache, out)
        cache.unlink()

        results.append({
            "path": rel(out),
            "status": "downloaded",
            "source": "ourairports",
            "table": table,
            "url": url,
            "rows": rows,
            "bytes": out.stat().st_size,
            "license": LICENSE,
        })
    return results
