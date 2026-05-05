"""One-shot: enable versioning + apply 90-day rolling lifecycle to the
media-backup bucket. Idempotent — safe to re-run.

Usage:
    python scripts/apply_bucket_lifecycle.py
    python scripts/apply_bucket_lifecycle.py --bucket media-backup

Requires: boto3 (already in the project), Railway CLI authenticated and
linked to the Retrouvailles project.

What it does:
  1. Pulls the bucket's S3 credentials from `railway bucket credentials`.
  2. Enables versioning (precondition for NoncurrentVersionExpiration).
  3. Applies a 90-day rolling lifecycle: noncurrent versions expire after
     90 days; current (live) versions are never auto-deleted.
  4. Reads the lifecycle config back and prints it for verification.

This is defense-in-depth — the backup_media command's path-dedup means
the bucket only grows when admins ADD photos, not when they replace
them. The lifecycle rule cleans up old versions in the rare case where
the same public_id is overwritten.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bucket", default="media-backup", help="Railway bucket name")
    args = parser.parse_args()

    print(f"[1/4] Fetching credentials for bucket '{args.bucket}'...")
    # shell=True on Windows so the .cmd shim Railway installs gets resolved.
    # On POSIX it's a no-op for the same single-string command.
    is_windows = sys.platform == "win32"
    cmd = (
        f'railway bucket credentials --bucket "{args.bucket}" --json'
        if is_windows
        else ["railway", "bucket", "credentials", "--bucket", args.bucket, "--json"]
    )
    try:
        raw = subprocess.check_output(cmd, text=True, shell=is_windows)
    except FileNotFoundError:
        print("ERROR: 'railway' CLI not found on PATH. Install from https://docs.railway.com/")
        return 1
    except subprocess.CalledProcessError as e:
        print(
            f"ERROR: railway bucket credentials failed (exit {e.returncode}). Are you "
            "authenticated and linked to the Retrouvailles project?"
        )
        return 1

    creds = json.loads(raw)
    print(f"      endpoint: {creds['endpoint']}")
    print(f"      region:   {creds['region']}")
    print(f"      bucket:   {creds['bucketName']}")

    try:
        import boto3
    except ImportError:
        print("ERROR: boto3 not installed. Run: pip install boto3")
        return 1

    s3 = boto3.client(
        "s3",
        endpoint_url=creds["endpoint"],
        aws_access_key_id=creds["accessKeyId"],
        aws_secret_access_key=creds["secretAccessKey"],
        region_name=creds["region"],
    )

    from botocore.exceptions import ClientError  # noqa: WPS433

    print("[2/4] Enabling versioning...")
    try:
        s3.put_bucket_versioning(
            Bucket=creds["bucketName"],
            VersioningConfiguration={"Status": "Enabled"},
        )
        versioning = s3.get_bucket_versioning(Bucket=creds["bucketName"])
        if versioning.get("Status") != "Enabled":
            print(f"      WARNING: versioning state after put = {versioning.get('Status')!r}")
        else:
            print("      versioning: Enabled")
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code == "BucketAlreadyExists":
            print(
                "      SKIP: backend rejected PutBucketVersioning with 'BucketAlreadyExists'.\n"
                "            This is the known Tigris-on-Railway response when versioning isn't\n"
                "            supported on this bucket (see docs/runbooks/restore.md §1.2).\n"
                "            Stopping here — without versioning, NoncurrentVersionExpiration is\n"
                "            a no-op and there is no useful lifecycle rule to apply.",
            )
            return 0
        raise

    print("[3/4] Applying 90-day rolling lifecycle rule...")
    try:
        s3.put_bucket_lifecycle_configuration(
            Bucket=creds["bucketName"],
            LifecycleConfiguration={
                "Rules": [
                    {
                        "ID": "rolling-90-day",
                        "Status": "Enabled",
                        "Filter": {"Prefix": ""},
                        "NoncurrentVersionExpiration": {"NoncurrentDays": 90},
                        "Expiration": {"ExpiredObjectDeleteMarker": True},
                    },
                ],
            },
        )
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "")
        if code in {"InvalidArgument", "InvalidRequest"}:
            print(
                f"      SKIP: backend rejected the rule shape ({code}: "
                f"{e.response['Error'].get('Message', '')[:120]}).\n"
                "            See docs/runbooks/restore.md §1.2 — Tigris-on-Railway only accepts\n"
                "            Expiration with explicit Days/Date, which would auto-delete the\n"
                "            backups themselves. No useful rule to apply on this backend.",
            )
            return 0
        raise

    print("[4/4] Verifying — current lifecycle config:")
    cfg = s3.get_bucket_lifecycle_configuration(Bucket=creds["bucketName"])
    print(json.dumps(cfg.get("Rules", []), indent=2, default=str))
    print("\nDone. Lifecycle is in effect. Re-running this script is safe (idempotent).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
