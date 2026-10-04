"""
BTS — Reporting Carrier On-Time Performance
============================================
Every US domestic flight operated by a reporting carrier: schedule, actual times,
delays (with cause), cancellations, diversions. ~540K flights/month.

Source : https://www.transtats.bts.gov/  (US government work — public domain)
Output : raw/flights/year=YYYY/month=MM/flights_YYYY_MM.csv.gz   (one file per month)

The original monthly file has 109 columns (mostly diversion detail); we keep the 35
used downstream, renamed to snake_case, values untouched.
"""

import zipfile
from pathlib import Path

from .common import CACHE_DIR, RAW_DIR, csv_to_gzip, download, rel

URL = (
    "https://transtats.bts.gov/PREZIP/"
    "On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month}.zip"
)
LICENSE = "Public domain (US Bureau of Transportation Statistics)"

COLUMNS = {
    "FlightDate": "flight_date",
    "Reporting_Airline": "reporting_airline",
    "IATA_CODE_Reporting_Airline": "airline_iata_code",
    "Tail_Number": "tail_number",
    "Flight_Number_Reporting_Airline": "flight_number",
    "Origin": "origin",
    "OriginCityName": "origin_city_name",
    "OriginState": "origin_state",
    "Dest": "dest",
    "DestCityName": "dest_city_name",
    "DestState": "dest_state",
    "CRSDepTime": "crs_dep_time",
    "DepTime": "dep_time",
    "DepDelay": "dep_delay",
    "DepDelayMinutes": "dep_delay_minutes",
    "DepDel15": "dep_del15",
    "TaxiOut": "taxi_out",
    "WheelsOff": "wheels_off",
    "WheelsOn": "wheels_on",
    "TaxiIn": "taxi_in",
    "CRSArrTime": "crs_arr_time",
    "ArrTime": "arr_time",
    "ArrDelay": "arr_delay",
    "ArrDelayMinutes": "arr_delay_minutes",
    "ArrDel15": "arr_del15",
    "Cancelled": "cancelled",
    "CancellationCode": "cancellation_code",
    "Diverted": "diverted",
    "CRSElapsedTime": "crs_elapsed_time",
    "ActualElapsedTime": "actual_elapsed_time",
    "AirTime": "air_time",
    "Distance": "distance",
    "CarrierDelay": "carrier_delay",
    "WeatherDelay": "weather_delay",
    "NASDelay": "nas_delay",
    "SecurityDelay": "security_delay",
    "LateAircraftDelay": "late_aircraft_delay",
}


def month_range(start: str, end: str) -> list[tuple[int, int]]:
    """'2019-01', '2025-12' -> [(2019, 1), ..., (2025, 12)]"""
    y, m = map(int, start.split("-"))
    end_y, end_m = map(int, end.split("-"))
    months = []
    while (y, m) <= (end_y, end_m):
        months.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return months


def output_path(year: int, month: int) -> Path:
    return RAW_DIR / "flights" / f"year={year}" / f"month={month:02d}" / f"flights_{year}_{month:02d}.csv.gz"


def fetch_month(year: int, month: int, keep_cache: bool = False) -> dict:
    """Download one month, keep the selected columns, write gzip. Idempotent."""
    out = output_path(year, month)
    url = URL.format(year=year, month=month)
    if out.exists():
        return {"path": rel(out), "status": "cached"}

    zip_path = download(url, CACHE_DIR / "bts" / f"bts_{year}_{month:02d}.zip")
    with zipfile.ZipFile(zip_path) as zf:
        csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        with zf.open(csv_name) as fh:
            rows = csv_to_gzip(fh, out, columns=COLUMNS)
    if not keep_cache:
        zip_path.unlink()

    return {
        "path": rel(out),
        "status": "downloaded",
        "source": "bts_on_time",
        "table": "flights",
        "url": url,
        "rows": rows,
        "bytes": out.stat().st_size,
        "license": LICENSE,
    }
