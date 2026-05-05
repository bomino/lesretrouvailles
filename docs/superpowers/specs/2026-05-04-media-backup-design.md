# P6a — Media Backup (Cloudinary → Railway object storage) Design

**Status:** Approved.
**Phase:** P6a (subset of master spec §8 Ops & RGPD).
**Last revised:** 2026-05-05 — pivoted from Backblaze B2 to Railway-native S3-compatible object storage.

## Goal

Weekly automated mirror of every Cloudinary-stored photo into a versioned, S3-compatible Railway bucket sitting in the same project as the application. Provides a recovery path independent of Cloudinary, and the foundation P6b's RGPD purge script will operate against.

## Non-goals (P6a)

- **Database backup.** Railway already runs daily Postgres snapshots (7-day retention). We document the restore procedure in the runbook; no app code involved.
- **Cross-cloud disaster recovery.** Master spec §8.2 originally called for off-cloud backup (GitHub Actions → Backblaze B2) to defend against "Railway dies." For our scale (~200 members, ~250 photos) we consciously accept Railway as a single point of failure for the backup target, in exchange for single-vendor operational simplicity. If we later need true cross-cloud redundancy, this design can extend by swapping `RealStorage` for any S3-compatible client.
- **Automatic restore-from-backup tooling.** Restore is operator-driven via the runbook (manual `aws s3 cp` + Cloudinary re-upload). Building a `restore_media` command is deferred until it's actually needed.
- **Cloudinary fallback view.** Master spec §8.2 mentioned a "Plan de bascule médias" if Cloudinary disappears. Documented in the runbook as a manual procedure; not a built-in code path.

## Architecture (§A)

Three components:

1. **`alumni/storage.py`** — thin client wrapper around `boto3` (S3 protocol) targeting Railway's bucket endpoint. Mirrors the `alumni/cloudinary.py` pattern exactly: `StorageClient` Protocol, `RealStorage` (boto3-backed, lazy import), `FakeStorage` (in-memory, records calls), `get_client()` resolver, `reset_fake_client()` test helper.

2. **`core/management/commands/backup_media.py`** — Django management command that walks the DB → enumerates `(public_id, storage_path)` pairs from `Member`, `Memory`, `InMemoriamEntry` → for each pair: `head_file(path)` skip-if-present → `cloudinary.download(public_id)` → `storage.upload_file(path, content)` → tally + report. Exits non-zero if success rate < 95%.

3. **Runbook (`docs/runbooks/restore.md`)** — operator-driven one-time provisioning (`railway bucket add`, set lifecycle policy, create cron service, wire variables) plus restore + drill procedures.

The cron itself is a Railway scheduled service named `media-backup-cron`, sibling to the main `lesretrouvailles` service in the same Railway project, sharing the same Docker image. Cron schedule: weekly `0 3 * * 0` (Sunday 03:00 UTC), per master spec §8.2.

## Storage client interface (§B.1)

```python
class StorageClient(Protocol):
    def head_file(self, path: str) -> dict[str, Any] | None: ...
    def upload_file(self, path: str, content: bytes) -> str: ...
    def list_versions(self, prefix: str) -> list[dict[str, Any]]: ...
    def delete_version(self, file_id: str) -> None: ...
```

Method shapes mirror what was originally B2-shaped, and remain S3-natural:

- `head_file(path)` → returns `{"file_id": str, "size": int}` or `None`. In S3 terms: `head_object`. Used for path-dedup.
- `upload_file(path, content)` → returns the object's S3 version ID (or empty string if versioning disabled). In S3 terms: `put_object`.
- `list_versions(prefix)` → returns ordered list of `{"file_id", "path", "size"}` for all versions under the prefix. In S3 terms: `list_object_versions`. Used by P6b's purge script.
- `delete_version(file_id)` → S3 `delete_object` with `VersionId`. Used by P6b.

## `backup_media` command (§B.2)

Pseudocode:

```
photo_ids = collect_photo_public_ids()  # union of Member, Memory, InMemoriamEntry
storage  = storage.get_client()
cloud    = cloudinary.get_client()

for public_id in photo_ids:
    storage_path = public_id  # 1:1 mirror
    try:
        if storage.head_file(storage_path) is not None:
            skipped += 1; continue
        content = cloud.download(public_id)
        storage.upload_file(storage_path, content)
        succeeded += 1
    except Exception as e:
        log.warning("backup_media: failed %s — %s", public_id, e)
        failed += 1

attempted = succeeded + failed
if attempted == 0:
    print("backup_media: 0 attempted, {skipped} skipped (already backed up)")
    return
print(f"backup_media: {succeeded} uploaded, {skipped} skipped, {failed} failed (success rate {rate:.1%})")
if rate < 0.95:
    sys.exit(1)
```

Design decisions (§B.2.1):

- **Path dedup, not hash dedup.** The bucket path is the Cloudinary `public_id` verbatim. `head_file(path)` returning a hit is sufficient evidence the photo is backed up. Simpler than maintaining a manifest, correct for our use case (admin-curated photos with stable `public_id`s).
- **Bucket versioning on.** Even though we deduplicate on path, leaving S3 versioning enabled means accidental overwrites or deletes are recoverable for the lifecycle window (90 days).
- **95% success-rate exit threshold** instead of "fail on any single error." Cloudinary occasionally returns 5xx flakes; we don't want every weekly run to alert on transient noise. If half a run silently 403s though, the threshold catches it.
- **Continue-on-error per photo.** A single failure does not abort the run.
- **Empty DB exits 0.** No photos to back up is not an error.
- **Hardcoded model list.** Future phases adding a `photo_public_id` field must update `_collect_photo_public_ids()`. Acceptable until ≥5 such models exist; at that point a plug-in registry is warranted.

## Cloudinary `download()` extension (§B.3)

`alumni/cloudinary.py` gains:

```python
def download(self, public_id: str) -> bytes: ...
```

on the Protocol, on `RealCloudinary` (uses SDK's `api.resource(public_id)` to get the secure_url, then `urllib.request.urlopen` to fetch the bytes — no extra dependency), and on `FakeCloudinary` (returns deterministic bytes derived from the public_id; records calls for assertions).

## Settings (§F)

Stable Django setting names, regardless of which provider Railway exposes:

```python
# alumni/settings/base.py
STORAGE_CLIENT_PATH       = env("STORAGE_CLIENT_PATH",       default="alumni.storage.FakeStorage")
STORAGE_BUCKET_NAME       = env("STORAGE_BUCKET_NAME",       default="")
STORAGE_ENDPOINT_URL      = env("STORAGE_ENDPOINT_URL",      default="")
STORAGE_ACCESS_KEY_ID     = env("STORAGE_ACCESS_KEY_ID",     default="")
STORAGE_SECRET_ACCESS_KEY = env("STORAGE_SECRET_ACCESS_KEY", default="")
STORAGE_REGION            = env("STORAGE_REGION",            default="auto")
STORAGE_BACKUP_REQUIRED   = env.bool("STORAGE_BACKUP_REQUIRED", default=False)
```

`alumni/settings/staging.py` adds a boot-time guard mirroring the existing Cloudinary one:

```python
if STORAGE_BACKUP_REQUIRED and STORAGE_CLIENT_PATH.endswith("RealStorage"):
    if not all([STORAGE_BUCKET_NAME, STORAGE_ENDPOINT_URL,
                STORAGE_ACCESS_KEY_ID, STORAGE_SECRET_ACCESS_KEY]):
        raise ImproperlyConfigured("STORAGE_BACKUP_REQUIRED=true with RealStorage selected, "
                                   "but one or more STORAGE_* credentials are missing.")
```

`STORAGE_BACKUP_REQUIRED=true` is set on the `media-backup-cron` service only; the web service leaves it unset (web doesn't need backup credentials).

The runbook documents how the operator wires Railway's bucket-credential variable references (e.g. `${{ MyBucket.BUCKET_ENDPOINT }}`) into these `STORAGE_*` env vars on the `media-backup-cron` service. Decoupling the Django setting names from Railway's env-var convention means a future provider swap (or running locally against minio) doesn't require code changes.

## Default in test mode

`FakeStorage` is the default when `STORAGE_CLIENT_PATH` is unset, mirroring `CLOUDINARY_CLIENT_PATH`'s `FakeCloudinary` default. This means `pytest` Just Works: no `boto3` calls leak in tests.

## Tests (§E)

| File | Count | Coverage |
|---|---|---|
| `alumni/tests/test_cloudinary_download.py` | 2 | `FakeCloudinary.download()` returns deterministic bytes per public_id; records calls. |
| `alumni/tests/test_storage.py` | 4 | `get_client()` returns FakeStorage singleton; `head_file` returns None for unknown path; `upload_file` makes subsequent `head_file` succeed; `reset_fake_client` clears state. |
| `core/tests/test_backup_media.py` | 6 | walks 3 model sources; skips when `head_file` hits; uploads when miss; continues on per-photo failure; exits 1 when rate < 95%; exits 0 silently when DB empty. |

Total: 12 new tests.

## Dependencies (§G)

- New: `boto3>=1.34` — added to `pyproject.toml`, `requirements.txt`, and the `Dockerfile` runtime install block. `boto3` is lazy-imported in `RealStorage.__init__` so the test environment isn't impacted.
- Removed: nothing. (The previous plan added `b2sdk`; this design never adds it.)

## File touch list (§H)

### Create
- `alumni/storage.py`
- `alumni/tests/test_storage.py`
- `alumni/tests/test_cloudinary_download.py`
- `core/management/__init__.py`
- `core/management/commands/__init__.py`
- `core/management/commands/backup_media.py`
- `core/tests/test_backup_media.py` (if `core/tests/` exists; else create it too)
- `docs/runbooks/restore.md`

### Modify
- `alumni/cloudinary.py` — add `download(public_id) -> bytes` to Protocol + Real + Fake
- `alumni/settings/base.py` — `STORAGE_*` env wiring
- `alumni/settings/staging.py` — boot-time guard
- `pyproject.toml` — add `boto3>=1.34`
- `requirements.txt` — add `boto3>=1.34`
- `Dockerfile` — add `"boto3>=1.34"` to runtime pip install
- `docs/superpowers/STATUS.md` — mark P6a complete after ship

### Delete
- None. (Old branch's `alumni/b2.py` and `alumni/management/` were never on `main`; we start fresh from `main`.)

## Manual provisioning (§I — runbook scope, not in code)

- One-time: Railway bucket creation, lifecycle rule (90-day rolling retention via S3 lifecycle), `media-backup-cron` service creation, env var wiring, first-run validation.
- Recurring: 90-day restore drills.

The runbook is the source of truth.

## Risks (§J)

| Risk | Mitigation |
|---|---|
| Railway account suspension takes down both app AND backup simultaneously | Accepted at our scale. Document upgrade path: a P-future phase can mirror to a true off-cloud target by adding a second `StorageClient` and writing both. |
| `boto3` is heavy (~10MB) | Lazy-imported in `RealStorage`; the cron service is the only place it runs. The web service container ships boto3 too, but Python doesn't load it until an import. |
| Bucket credential leak | Mitigated by Railway-side IAM-equivalent: the bucket's credentials are scoped to a single bucket. We can rotate by regenerating credentials in the Railway dashboard. |
| Cron service silently fails (Railway scheduler bug, image won't build) | The 95% threshold + Railway's deploy-status notifications surface failures. Operator's quarterly drill is the human backstop. |
| Photo-bearing model added without updating `_collect_photo_public_ids()` | Documented in module docstring; nyquist-style risk until ≥5 such models exist. |

## Reasoning §A — why Railway-native instead of B2

Real-world vendor picture: **Railway** (app + Postgres) and **Cloudinary** (primary media storage + transforms) are already in production. The original master spec §8.2 added Backblaze B2 as a *third* vendor for true cross-cloud diversity ("any one of {Railway, Cloudinary, B2} disappears, we still recover"). For our scale and operating model, we made an explicit downgrade trade:

- **Operational cost of a third vendor** (account, billing, credentials in 1Password, separate dashboard, separate runbook section, separate alerting) is non-trivial and recurring.
- **Probability of dual-cloud failure** (Railway *and* Cloudinary lose data simultaneously, in a window before we can manually restore from somewhere else) is very low for a 200-member alumni site.
- **Probability of single-cloud failure that backup defends against** (Cloudinary loses our account, has data corruption, gets acquired) is the dominant scenario.

A Railway bucket sits inside the Railway project we already pay for: no new account, no new bill, same dashboard, same runbook section as the rest of Railway. We still have Cloudinary, but we don't add a third vendor surface to operate. **Same defense against the dominant failure (Cloudinary disappears), strictly less operational surface than the master spec design.**

If a future phase needs to upgrade to true off-cloud DR (e.g., the membership grows past a few thousand and the photos become irreplaceable cultural archives), the architecture supports it cleanly: add a second `StorageClient` instance and have `backup_media` write to both. Spec §B.1 keeps the protocol minimal precisely so this swap stays cheap.
