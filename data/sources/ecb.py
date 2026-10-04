"""
ECB euro foreign exchange reference rates → dbt seed
=====================================================
Daily reference rates (units of currency per 1 EUR) published by the European Central
Bank. We turn them into USD per 1 unit of each currency NomadHub prices are in, with
weekends/holidays forward-filled so every calendar day has a rate.

Source : https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/
         (free reuse with attribution: "Source: ECB")
Output : nomad_hub/seeds/fx_rates_daily.csv   rate_date, currency_code, usd_per_unit
"""

import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

from .common import HEADERS

URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"
LICENSE = "ECB euro reference rates — free reuse with attribution (Source: ECB)"
CURRENCIES = ["EUR", "GBP", "TRY", "JPY"]          # + USD itself (always 1.0)
START_DATE = "2014-01-01"                           # earliest signup in the generated data
SEED_PATH = Path(__file__).resolve().parents[2] / "nomad_hub" / "seeds" / "fx_rates_daily.csv"


def build_seed() -> dict:
    resp = requests.get(URL, headers=HEADERS, timeout=120)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        raw = pd.read_csv(zf.open(zf.namelist()[0]), usecols=["Date", "USD", "GBP", "TRY", "JPY"])

    raw["Date"] = pd.to_datetime(raw["Date"])
    raw = raw[raw["Date"] >= START_DATE].set_index("Date").sort_index()
    days = pd.date_range(START_DATE, raw.index.max(), freq="D")
    eur = raw.apply(pd.to_numeric, errors="coerce").reindex(days).ffill()

    usd_per_unit = pd.DataFrame({
        "EUR": eur["USD"],                 # USD per 1 EUR
        "GBP": eur["USD"] / eur["GBP"],
        "TRY": eur["USD"] / eur["TRY"],
        "JPY": eur["USD"] / eur["JPY"],
        "USD": 1.0,
    }, index=days)

    seed = (
        usd_per_unit.rename_axis("rate_date").reset_index()
        .melt(id_vars="rate_date", var_name="currency_code", value_name="usd_per_unit")
        .dropna()
        .sort_values(["rate_date", "currency_code"])
    )
    seed["rate_date"] = seed["rate_date"].dt.strftime("%Y-%m-%d")
    seed["usd_per_unit"] = seed["usd_per_unit"].round(8)
    seed.to_csv(SEED_PATH, index=False)

    return {
        "path": str(SEED_PATH.relative_to(SEED_PATH.parents[2])),
        "rows": len(seed),
        "first_date": seed["rate_date"].min(),
        "last_date": seed["rate_date"].max(),
        "license": LICENSE,
    }
