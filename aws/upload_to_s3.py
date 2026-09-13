"""
NomadHub — S3 Upload Utility
==============================
Uploads generated CSV files to an S3 bucket under raw/<table>/<file>.csv
with a progress bar per file and parallel uploads.

Usage:
    python upload_to_s3.py --bucket my-nomad-hub-bucket
    python upload_to_s3.py --bucket my-nomad-hub-bucket --data-dir ../data
    python upload_to_s3.py --bucket my-nomad-hub-bucket --prefix raw --workers 4
"""

import argparse
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from tqdm import tqdm

# Tables to upload (order matters for dependency awareness)
TABLES = [
    "countries",
    "airports",
    "hotels",
    "users",
    "flights",
    "hotel_bookings",
    "reviews",
]


class S3Uploader:
    def __init__(self, bucket: str, prefix: str, data_dir: Path):
        self.bucket = bucket
        self.prefix = prefix.rstrip("/")
        self.data_dir = data_dir
        self.s3 = boto3.client("s3")

    def _get_s3_key(self, table: str, filename: str) -> str:
        return f"{self.prefix}/{table}/{filename}"

    def upload_file(self, table: str) -> dict:
        """Upload a single CSV file to S3 with progress tracking."""
        csv_path = self.data_dir / f"{table}.csv"
        if not csv_path.exists():
            return {"table": table, "status": "skipped", "reason": "file not found"}

        file_size = csv_path.stat().st_size
        s3_key = self._get_s3_key(table, csv_path.name)
        uploaded_bytes = [0]

        def progress_callback(bytes_transferred):
            uploaded_bytes[0] += bytes_transferred
            pbar.update(bytes_transferred)

        try:
            with tqdm(
                total=file_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                desc=f"  ⬆ {table}",
                leave=True,
            ) as pbar:
                self.s3.upload_file(
                    str(csv_path),
                    self.bucket,
                    s3_key,
                    Callback=progress_callback,
                )
            return {
                "table": table,
                "status": "success",
                "s3_key": f"s3://{self.bucket}/{s3_key}",
                "size_mb": round(file_size / 1_048_576, 1),
            }
        except ClientError as e:
            return {"table": table, "status": "error", "reason": str(e)}

    def verify_upload(self, table: str) -> bool:
        """Verify that an uploaded file is accessible in S3."""
        s3_key = self._get_s3_key(table, f"{table}.csv")
        try:
            self.s3.head_object(Bucket=self.bucket, Key=s3_key)
            return True
        except ClientError:
            return False


def main() -> None:
    parser = argparse.ArgumentParser(description="NomadHub S3 uploader")
    parser.add_argument("--bucket", required=True, help="S3 bucket name")
    parser.add_argument("--prefix", default="raw", help="S3 key prefix (default: raw)")
    parser.add_argument("--data-dir", default=".", help="Directory containing CSVs (default: .)")
    parser.add_argument("--workers", type=int, default=2, help="Parallel upload workers (default: 2)")
    parser.add_argument("--tables", nargs="+", default=TABLES, choices=TABLES,
                        help="Which tables to upload (default: all)")
    parser.add_argument("--verify", action="store_true", help="Verify uploads after completion")
    args = parser.parse_args()

    data_dir = Path(args.data_dir).resolve()
    if not data_dir.exists():
        print(f"❌ Data directory not found: {data_dir}")
        sys.exit(1)

    print(f"\n{'=' * 60}")
    print(f"  NomadHub S3 Upload")
    print(f"{'=' * 60}")
    print(f"  Bucket  : s3://{args.bucket}/{args.prefix}/")
    print(f"  Data dir: {data_dir}")
    print(f"  Workers : {args.workers}")
    print(f"  Tables  : {', '.join(args.tables)}")
    print(f"{'=' * 60}\n")

    # Validate AWS credentials early
    uploader = S3Uploader(args.bucket, args.prefix, data_dir)
    try:
        uploader.s3.head_bucket(Bucket=args.bucket)
        print(f"  ✅ Bucket accessible: s3://{args.bucket}\n")
    except NoCredentialsError:
        print("❌ AWS credentials not found. Run: aws configure")
        sys.exit(1)
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "404":
            print(f"❌ Bucket not found: {args.bucket}")
        elif code == "403":
            print(f"❌ Access denied to bucket: {args.bucket}")
        else:
            print(f"❌ Bucket error: {e}")
        sys.exit(1)

    # Upload files (parallel for large files; sequential for small dims)
    small_tables = [t for t in args.tables if t in ("countries", "airports", "hotels", "users")]
    large_tables = [t for t in args.tables if t in ("flights", "hotel_bookings", "reviews")]

    results = []

    # Upload dimension tables sequentially
    if small_tables:
        print("📦 Uploading dimension tables...")
        for table in small_tables:
            result = uploader.upload_file(table)
            results.append(result)

    # Upload fact/large tables in parallel
    if large_tables:
        print("\n📦 Uploading large tables (parallel)...")
        with ThreadPoolExecutor(max_workers=min(args.workers, len(large_tables))) as executor:
            futures = {executor.submit(uploader.upload_file, t): t for t in large_tables}
            for future in as_completed(futures):
                result = future.result()
                results.append(result)

    # Summary
    print(f"\n{'=' * 60}")
    print("  Upload Summary")
    print(f"{'=' * 60}")
    success_count = 0
    for r in sorted(results, key=lambda x: x["table"]):
        if r["status"] == "success":
            print(f"  ✅ {r['table']:<20} {r['size_mb']:>8.1f} MB  →  {r['s3_key']}")
            success_count += 1
        elif r["status"] == "skipped":
            print(f"  ⏭  {r['table']:<20} skipped ({r['reason']})")
        else:
            print(f"  ❌ {r['table']:<20} FAILED: {r['reason']}")

    print(f"\n  {success_count}/{len(results)} tables uploaded successfully.")

    # Verify
    if args.verify:
        print("\n🔍 Verifying uploads...")
        for r in results:
            if r["status"] == "success":
                ok = uploader.verify_upload(r["table"])
                status_icon = "✅" if ok else "❌"
                print(f"  {status_icon} {r['table']}")

    print(f"\n{'=' * 60}")
    print("  Next step: Run snowflake/02_storage_integration.sql in Snowsight")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
