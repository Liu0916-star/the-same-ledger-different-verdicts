"""Download the two v2 extraction tables to data/v2/*.parquet.

Reads with tabledata.list (no query cost). Auth: the active gcloud user token.
Usage: python sql/download_v2.py <project_id>
"""
import subprocess, sys
from pathlib import Path
import google.oauth2.credentials as oc
from google.cloud import bigquery

project = sys.argv[1]
token = subprocess.check_output(
    [str(Path.home() / "google-cloud-sdk/bin/gcloud"), "auth", "print-access-token"],
    text=True).strip()
client = bigquery.Client(project=project, credentials=oc.Credentials(token))
out = Path(__file__).resolve().parent.parent / "data" / "v2"
out.mkdir(parents=True, exist_ok=True)
for name in ("v2_transfers", "v2_balances"):
    tbl = client.get_table(f"{project}.conc.{name}")
    df = client.list_rows(tbl, page_size=50_000).to_dataframe(create_bqstorage_client=False)
    # BIGNUMERIC -> exact decimal string (never float)
    for c in df.columns:
        if df[c].dtype == object and c.endswith("_raw"):
            df[c] = df[c].astype(str)
    df.to_parquet(out / f"{name}.parquet", index=False)
    print(name, len(df), "rows ->", out / f"{name}.parquet")
