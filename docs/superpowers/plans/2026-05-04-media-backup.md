# P6a — Media Backup (Cloudinary → Railway object storage) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Weekly automated mirror of every Cloudinary-stored photo into a versioned, S3-compatible Railway bucket living in the same project as the application. Provides a recovery path independent of Cloudinary, and the foundation P6b's RGPD purge script will operate against.

**Architecture:** New `alumni/storage.py` thin client wrapper (real boto3 + fake) mirroring the existing `alumni/cloudinary.py` pattern. New `python manage.py backup_media` Django management command (in `core/management/commands/`) walks DB → enumerates `(public_id, storage_path)` pairs → path-dedup via `storage.head_file` → uploads new content. Runs as a Railway scheduled service (`media-backup-cron`, weekly Sunday 03:00 UTC) sharing the same Docker image as the main app and pointed at a Railway-native S3-compatible bucket sitting in the same Railway project.

**Tech Stack:** Django 5, Postgres ArrayField (existing), `boto3` (new pip dep, lazy-imported), Cloudinary admin API for original-bytes download, Railway cron service for scheduling, Railway bucket as the S3 backend.

**Spec:** [`docs/superpowers/specs/2026-05-04-media-backup-design.md`](../specs/2026-05-04-media-backup-design.md)

---

## File touch list

### Create

- `alumni/storage.py`
- `alumni/tests/test_storage.py`
- `alumni/tests/test_cloudinary_download.py`
- `core/management/__init__.py`
- `core/management/commands/__init__.py`
- `core/management/commands/backup_media.py`
- `core/tests/test_backup_media.py`
- `docs/runbooks/restore.md`

### Modify

- `alumni/cloudinary.py` — add `download(public_id) -> bytes` to the Protocol, RealCloudinary, and FakeCloudinary
- `alumni/settings/base.py` — `STORAGE_CLIENT_PATH`, `STORAGE_BUCKET_NAME`, `STORAGE_ENDPOINT_URL`, `STORAGE_ACCESS_KEY_ID`, `STORAGE_SECRET_ACCESS_KEY`, `STORAGE_REGION`, `STORAGE_BACKUP_REQUIRED`
- `alumni/settings/staging.py` — boot-time `ImproperlyConfigured` guard mirroring the existing Cloudinary one
- `pyproject.toml` — add `boto3>=1.34`
- `requirements.txt` — add `boto3>=1.34`
- `Dockerfile` — add `"boto3>=1.34"` to the runtime pip install block
- `docs/superpowers/STATUS.md` — mark P6a complete after ship

---

## Task 1: Cloudinary `download()` method

**Why first:** Foundation. The backup command depends on this method existing. Trivial diff (one method on three places). TDD-friendly in isolation.

**Files:**
- Modify: `alumni/cloudinary.py`
- Create: `alumni/tests/test_cloudinary_download.py`

- [ ] **Step 1: Write the failing tests**
- [ ] **Step 2: Run tests, expect failure** (`AttributeError: 'FakeCloudinary' object has no attribute 'download'`)
- [ ] **Step 3: Add `download()` to the Protocol, `RealCloudinary`, and `FakeCloudinary`** — including a new `download_calls` list on FakeCloudinary's `__init__`.
- [ ] **Step 4: Run tests, expect pass**
- [ ] **Step 5: Run full suite — no regressions**
- [ ] **Step 6: Commit**

```bash
git add alumni/cloudinary.py alumni/tests/test_cloudinary_download.py
git commit -m "feat(cloudinary): add download(public_id) -> bytes method"
```

---

## Task 2: Storage client wrapper + settings + boto3 dep

**Files:**
- Create: `alumni/storage.py`, `alumni/tests/test_storage.py`
- Modify: `alumni/settings/base.py`, `alumni/settings/staging.py`, `pyproject.toml`, `requirements.txt`, `Dockerfile`

`alumni/storage.py` is a near-clone of `alumni/cloudinary.py`'s structure: a `StorageClient` Protocol with `head_file`, `upload_file`, `list_versions`, `delete_version`; a `RealStorage` class that lazy-imports `boto3` and wraps the S3 API; a `FakeStorage` class that records calls; `get_client()` resolves from `STORAGE_CLIENT_PATH` with FakeStorage as a singleton in test mode; `reset_fake_client()` for fixture teardown.

`RealStorage` configures the boto3 client with:
- `endpoint_url=STORAGE_ENDPOINT_URL` (Railway's bucket endpoint)
- `aws_access_key_id=STORAGE_ACCESS_KEY_ID`
- `aws_secret_access_key=STORAGE_SECRET_ACCESS_KEY`
- `region_name=STORAGE_REGION` (default `"auto"` — Railway buckets don't use AWS regions)

Method mapping:
- `head_file(path)` → `s3.head_object(Bucket=B, Key=path)` → `{"file_id": VersionId, "size": ContentLength}` or `None` on `ClientError` 404.
- `upload_file(path, content)` → `s3.put_object(Bucket=B, Key=path, Body=content)` → returns `VersionId` if versioning enabled (else `""`).
- `list_versions(prefix)` → `s3.list_object_versions(Bucket=B, Prefix=prefix)` → list of `{"file_id", "path", "size"}`.
- `delete_version(file_id)` → caller passes both file_id and the path (or we look up via list_versions). To keep it cheap, signature accepts both: `delete_version(path, file_id)`.

**Settings to add to `alumni/settings/base.py`:**

```python
# Object storage — media backup target (P6a).
# Default points at FakeStorage so tests/dev never touch the network.
# Production cron service overrides STORAGE_CLIENT_PATH to RealStorage and
# sets the four credential vars from a Railway bucket reference.
STORAGE_CLIENT_PATH       = env("STORAGE_CLIENT_PATH",       default="alumni.storage.FakeStorage")
STORAGE_BUCKET_NAME       = env("STORAGE_BUCKET_NAME",       default="")
STORAGE_ENDPOINT_URL      = env("STORAGE_ENDPOINT_URL",      default="")
STORAGE_ACCESS_KEY_ID     = env("STORAGE_ACCESS_KEY_ID",     default="")
STORAGE_SECRET_ACCESS_KEY = env("STORAGE_SECRET_ACCESS_KEY", default="")
STORAGE_REGION            = env("STORAGE_REGION",            default="auto")
STORAGE_BACKUP_REQUIRED   = env.bool("STORAGE_BACKUP_REQUIRED", default=False)
```

**Boot-time guard in `alumni/settings/staging.py`:**

Add the `STORAGE_*` names to the `from .base import ...` line and append after the existing Cloudinary guard:

```python
if STORAGE_BACKUP_REQUIRED and STORAGE_CLIENT_PATH.endswith("RealStorage"):
    if not all([STORAGE_BUCKET_NAME, STORAGE_ENDPOINT_URL,
                STORAGE_ACCESS_KEY_ID, STORAGE_SECRET_ACCESS_KEY]):
        raise ImproperlyConfigured(
            "STORAGE_BACKUP_REQUIRED=true with RealStorage selected, but one or "
            "more of STORAGE_BUCKET_NAME / STORAGE_ENDPOINT_URL / "
            "STORAGE_ACCESS_KEY_ID / STORAGE_SECRET_ACCESS_KEY is missing."
        )
```

**Dependency wiring:** add `"boto3>=1.34"` to `pyproject.toml`'s `dependencies`, to `requirements.txt`, and to the `Dockerfile`'s runtime pip install block. Insert next to `bleach>=6.0` to keep alphabetical-ish ordering.

- [ ] **Step 1: Write the failing tests** (test_get_client_returns_fake_singleton, test_head_file_returns_none_for_unknown_path, test_upload_file_makes_subsequent_head_succeed, test_reset_fake_client_clears_state)
- [ ] **Step 2: Run tests, expect failure** (`ModuleNotFoundError: No module named 'alumni.storage'`)
- [ ] **Step 3: Implement `alumni/storage.py`**
- [ ] **Step 4: Add `STORAGE_*` settings to base.py**
- [ ] **Step 5: Add the boot guard to staging.py**
- [ ] **Step 6: Add `boto3` to pyproject/requirements/Dockerfile**
- [ ] **Step 7: Run tests, expect pass**
- [ ] **Step 8: Run full suite — no regressions**
- [ ] **Step 9: Commit**

```bash
git add alumni/storage.py alumni/tests/test_storage.py alumni/settings/base.py alumni/settings/staging.py pyproject.toml requirements.txt Dockerfile
git commit -m "feat(storage): S3-compatible client wrapper + settings + boto3 dep"
```

---

## Task 3: `backup_media` management command

**Files:**
- Create: `core/management/__init__.py`, `core/management/commands/__init__.py`
- Create: `core/management/commands/backup_media.py`, `core/tests/test_backup_media.py`

The command lives in `core/` (already an installed app) so Django's command-discovery picks it up without adding a new app config.

`_collect_photo_public_ids()` queries `Member`, `Memory`, `InMemoriamEntry` for non-empty `photo_public_id`, dedupes, and returns a sorted list. New phases that add a `photo_public_id`-bearing model must update this function.

`Command.handle()` walks the list, applies path-dedup via `storage.head_file()`, downloads from Cloudinary, uploads to storage, tallies. Per-photo failures are caught with `logger.warning` and counted but do not abort. After the loop: if no attempts, log "0 attempted" and return; otherwise log the summary and `sys.exit(1)` if `succeeded / attempted < 0.95`.

**Tests** (6, all in `core/tests/test_backup_media.py`):

1. `test_walks_all_three_model_sources` — Member + Memory + InMemoriamEntry all enumerated and uploaded.
2. `test_skips_when_storage_already_has_path` — pre-populated bucket short-circuits Cloudinary download AND storage upload.
3. `test_uploads_when_head_returns_none` — full path: download → upload happens.
4. `test_continues_on_per_photo_failure` — one Cloudinary 503 doesn't abort; other photos still upload.
5. `test_exits_nonzero_when_success_rate_below_95` — total outage → `SystemExit(1)`.
6. `test_empty_db_exits_silently_zero` — no photos: log + exit 0 (no SystemExit).

The fixture `reset_fakes` calls `storage.reset_fake_client()` and `cloudinary.reset_fake_client()` between tests so call lists don't leak.

- [ ] **Step 1: Create empty `__init__.py` files in `core/management/` and `core/management/commands/`**
- [ ] **Step 2: Write the failing tests**
- [ ] **Step 3: Run tests, expect failure** (`CommandError: Unknown command: 'backup_media'`)
- [ ] **Step 4: Implement `core/management/commands/backup_media.py`**
- [ ] **Step 5: Run tests, expect pass (6 passing)**
- [ ] **Step 6: Run full suite — no regressions**
- [ ] **Step 7: Commit**

```bash
git add core/management/ core/tests/test_backup_media.py
git commit -m "feat(backup): backup_media management command (path-dedup + 95% threshold)"
```

---

## Task 4: Restore + provisioning runbook

**Files:**
- Create: `docs/runbooks/restore.md`

Operator-facing runbook. No code, no tests. Covers:

1. **First-time provisioning** — create a Railway bucket via `railway bucket add`, set lifecycle (S3 lifecycle rule for 90-day rolling retention), create the `media-backup-cron` Railway service from the same Dockerfile with start command `python manage.py backup_media` and cron schedule `0 3 * * 0`, wire the bucket's S3 credential variables (`${{ MyBucket.X }}`) into the cron service's `STORAGE_*` env vars, set `STORAGE_BACKUP_REQUIRED=true`.
2. **First-run validation** — manually trigger the cron, check logs for `"backup_media: N uploaded, ..."`, verify objects appear in the bucket via `aws s3 ls --endpoint-url=$STORAGE_ENDPOINT_URL`.
3. **Verifying ongoing backups** — Railway deploy log inspection.
4. **Restore a single photo** — `aws s3 cp s3://...` then `cld uploader upload --public_id=... --overwrite=true`.
5. **Quarterly restore drill** — pick a random photo, restore to a temp location, sha1sum compare.
6. **Cloudinary disaster scenario** — manual fallback procedure (sync bucket to a temp host, point DNS).
7. **Database restore** — Railway Postgres snapshots (7-day retention).
8. **Cost monitoring** — bucket storage at our scale stays under Railway's plan ceiling; Cloudinary downloads count as transformations (well within the free tier).

- [ ] **Step 1: Write `docs/runbooks/restore.md`**
- [ ] **Step 2: Commit**

```bash
git add docs/runbooks/restore.md
git commit -m "docs(runbook): media-backup provisioning + restore + drill procedure"
```

---

## Task 5: STATUS update + final verification

**Files:**
- Modify: `docs/superpowers/STATUS.md`

- [ ] **Step 1: Update the Phase Index in `docs/superpowers/STATUS.md`** — replace the current `P6` row with two rows (`P6a` complete, `P6` in progress).
- [ ] **Step 2: Append a P6a section** with shipping date, plan/spec links, test count, task table with commit shas, and the notable design decisions block (re-emphasizing the Railway-native pivot vs the master spec).
- [ ] **Step 3: Run the full test suite one final time** — `pytest -q`.
- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/STATUS.md
git commit -m "docs(p6a): mark P6a complete in STATUS"
```

- [ ] **Step 5: Verify the branch is clean and ready to ship** — `git status`, `git log --oneline main..HEAD` should show ~6–7 commits.

---

## Self-review summary

**Spec coverage:**
- §A architecture — Tasks 2 (storage client) + 3 (command) + Task 4 runbook (Railway service creation) cover the full architecture.
- §B.1 storage client — Task 2.
- §B.2 backup_media command — Task 3.
- §B.3 Cloudinary download() extension — Task 1.
- §F settings — Task 2 (base.py + staging.py guard).
- §G `boto3` dep — Task 2.
- §H file touch list — covered.
- §I manual provisioning — Task 4 runbook; not in code.
- §J risks — documented in spec + runbook; no code action.

**Type/name consistency:**
- Module: `alumni.storage`. Classes: `StorageClient`, `RealStorage`, `FakeStorage`. Functions: `get_client()`, `reset_fake_client()`. Methods: `head_file`, `upload_file`, `list_versions`, `delete_version`. All consistent across Tasks 2, 3.
- Settings: `STORAGE_CLIENT_PATH`, `STORAGE_BUCKET_NAME`, `STORAGE_ENDPOINT_URL`, `STORAGE_ACCESS_KEY_ID`, `STORAGE_SECRET_ACCESS_KEY`, `STORAGE_REGION`, `STORAGE_BACKUP_REQUIRED` — consistent across Tasks 2 and the runbook.
- Cron cadence: `0 3 * * 0` — runbook + STATUS notable decisions.
- Success threshold: 95% — Task 3 implementation + tests.

No placeholder strings or TBD markers in code. The runbook contains operator-fillable values (`<bucket-name>`, `<endpoint>`, `<key>`) which are intentional.
