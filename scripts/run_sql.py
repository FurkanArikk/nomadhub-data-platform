"""
Run a Snowflake SQL file as one of the NomadHub service users (key-pair auth).

    python scripts/run_sql.py snowflake/01_raw_tables.sql
    python scripts/run_sql.py snowflake/02_copy_into.sql --user AIRFLOW_SVC

Needs: pip install "snowflake-connector-python>=3.12"
Reads SNOWFLAKE_ACCOUNT (ORGNAME-ACCOUNTNAME) from the environment, or falls back to
`terraform output -raw snowflake_account`. The private key is read from
~/.nomadhub/keys/<user>_rsa_key.p8 (override with --key-dir).
"""

import argparse
import os
import subprocess
import time
from pathlib import Path

import snowflake.connector

ROOT = Path(__file__).resolve().parent.parent


def account() -> str:
    if os.environ.get("SNOWFLAKE_ACCOUNT"):
        return os.environ["SNOWFLAKE_ACCOUNT"]
    return subprocess.check_output(
        ["terraform", f"-chdir={ROOT / 'terraform'}", "output", "-raw", "snowflake_account"], text=True
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a SQL file on Snowflake")
    parser.add_argument("sql_file", type=Path)
    parser.add_argument("--user", default="AIRFLOW_SVC")
    parser.add_argument("--key-dir", default="~/.nomadhub/keys")
    args = parser.parse_args()

    key_path = Path(args.key_dir).expanduser() / f"{args.user.lower()}_rsa_key.p8"
    conn = snowflake.connector.connect(
        account=account(),
        user=args.user,
        authenticator="SNOWFLAKE_JWT",
        private_key_file=str(key_path),
    )
    print(f"Connected to {conn.account} as {args.user}; running {args.sql_file}")
    t0 = time.time()
    try:
        for cursor in conn.execute_string(args.sql_file.read_text(), remove_comments=True):
            first_line = cursor.query.strip().splitlines()[0][:90]
            rows = cursor.fetchall() if cursor.description else []
            print(f"  ✓ {first_line}")
            if first_line.upper().startswith(("SELECT", "COPY")):
                for row in rows[:20]:
                    print(f"      {row}")
    finally:
        conn.close()
    print(f"Done in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
