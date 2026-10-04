"""
Shared helpers for the source downloaders
==========================================
- Resumable, retrying HTTP downloads (atomic: written to *.part, then renamed)
- Streaming CSV → selected-columns gzip CSV (constant memory, even for 35M-row files)
- A JSON manifest recording what was downloaded, from where, and under which license
"""

import gzip
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

DATA_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = DATA_DIR / "raw"          # mirrors s3://<bucket>/raw/
CACHE_DIR = DATA_DIR / ".cache"     # original downloads, deleted after processing
MANIFEST_PATH = RAW_DIR / "_manifest.json"

HEADERS = {"User-Agent": "NomadHub-portfolio-downloader/1.0 (educational data engineering project)"}
CHUNK_ROWS = 250_000


def download(url: str, dest: Path, retries: int = 4, timeout: int = 300) -> Path:
    """Stream `url` to `dest`. Skips if `dest` already exists; retries with backoff."""
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")

    for attempt in range(1, retries + 1):
        try:
            with requests.get(url, stream=True, timeout=timeout, headers=HEADERS) as resp:
                resp.raise_for_status()
                with open(tmp, "wb") as fh:
                    for block in resp.iter_content(chunk_size=1 << 20):
                        fh.write(block)
            tmp.rename(dest)
            return dest
        except requests.RequestException as exc:
            status = exc.response.status_code if exc.response is not None else None
            permanent = status is not None and 400 <= status < 500 and status != 429
            if permanent or attempt == retries:
                raise
            wait = 5 * 2**attempt
            print(f"  ⚠ {url} failed ({exc}); retry {attempt}/{retries - 1} in {wait}s")
            time.sleep(wait)
    return dest


def csv_to_gzip(
    src,
    dest: Path,
    columns: dict[str, str] | None = None,
    extra: dict[str, str] | None = None,
) -> int:
    """
    Stream a CSV (path or file object, gzip inferred from path) into a gzip CSV at `dest`.

    columns: source column -> output column. Output keeps exactly these columns, in this
             order; any missing from the source are emitted empty, so every file of a table
             has an identical layout (Snowflake COPY loads by position).
    extra:   constant columns prepended to every row (e.g. city, snapshot_date).
    All values are kept as raw strings — cleaning and typing happen in dbt staging.
    Returns the number of data rows written.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    extra = extra or {}
    rows = 0

    reader = pd.read_csv(
        src,
        dtype=str,
        keep_default_na=False,   # keep empty strings as-is; Snowflake maps them to NULL
        chunksize=CHUNK_ROWS,
        usecols=(lambda c: c in columns) if columns else None,
    )
    with gzip.open(tmp, "wt", encoding="utf-8", newline="") as out:
        for i, chunk in enumerate(reader):
            if columns:
                if i == 0:
                    missing = [c for c in columns if c not in chunk.columns]
                    if missing:
                        print(f"  ⚠ {dest.name}: source lacks {missing}; emitting them empty")
                chunk = chunk.reindex(columns=list(columns)).rename(columns=columns)
            for pos, (name, value) in enumerate(extra.items()):
                chunk.insert(pos, name, value)
            chunk.to_csv(out, index=False, header=(i == 0))
            rows += len(chunk)

    tmp.rename(dest)
    return rows


def update_manifest(entries: list[dict], replace_prefix: str | None = None) -> None:
    """
    Merge entries (keyed by their output path) into data/raw/_manifest.json.
    replace_prefix: first drop every existing entry under this path (for regenerated tables).
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else {}
    if replace_prefix:
        manifest = {k: v for k, v in manifest.items() if not k.startswith(replace_prefix)}
    now = datetime.now(UTC).isoformat(timespec="seconds")
    for entry in entries:
        manifest[entry["path"]] = {**entry, "recorded_at": now}
    MANIFEST_PATH.write_text(json.dumps(dict(sorted(manifest.items())), indent=2))


def rel(path: Path) -> str:
    """Path relative to data/raw — identical to the S3 key under raw/."""
    return path.relative_to(RAW_DIR).as_posix()
