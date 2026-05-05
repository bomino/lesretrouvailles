# Restore + media-backup runbook

**Services:**
- Backup target: a Railway-native S3-compatible bucket (project `Retrouvailles`).
- Cron: Railway service `media-backup-cron` (sibling of `lesretrouvailles` in the same project).
- Spec: [docs/superpowers/specs/2026-05-04-media-backup-design.md](../superpowers/specs/2026-05-04-media-backup-design.md)

---

## 1. First-time provisioning (one-shot)

### 1.1 Create the Railway bucket

From a terminal where the Railway CLI is linked to the project:

```bash
railway bucket add --name media-backup
```

(Or via the Railway dashboard → project `Retrouvailles` → **+ Create** → **Bucket**.)

Once created, capture the bucket's S3-compatible credentials. From the dashboard the bucket page exposes:

- `BUCKET_ENDPOINT` — S3 endpoint URL
- `BUCKET_ACCESS_KEY_ID`
- `BUCKET_SECRET_ACCESS_KEY`
- `BUCKET_NAME`

…or via CLI:

```bash
railway bucket credentials --bucket media-backup --json
```

Save those values in 1Password as "Retrouvailles media-backup bucket".

### 1.2 Versioning + lifecycle — SKIP (not supported by Tigris-on-Railway)

> **TL;DR — do not run any commands in this section.** As of 2026-05, Railway's bucket service uses Tigris (`storageapi.dev`) under the hood. Tigris's S3 implementation does not support the S3 APIs we'd need to apply a useful retention rule:
>
> - `PutBucketVersioning` returns `BucketAlreadyExists` (a misleading error meaning the operation isn't supported under these credentials/this bucket).
> - `PutBucketLifecycleConfiguration` only accepts rules with an explicit `Expiration` of `Days` or `Date`. It rejects `NoncurrentVersionExpiration` and `ExpiredObjectDeleteMarker` with: *"Lifecycle only supports expiration rule. Expiration rule with content days or dates only."*
>
> The only rule shape Tigris would accept is `{"Expiration": {"Days": N}}` — which would auto-delete every backed-up object after N days, the opposite of what we want.
>
> **What this means in practice:** there is no useful lifecycle rule to apply today. We accepted this when picking Railway-native storage (spec §J risks).

#### Why this is fine at our scale

The `backup_media` command uses **path dedup** — once a photo lands in the bucket at `<public_id>`, subsequent weekly runs skip it. The bucket only grows when admins add *new* photos. At ~200 members × a few MB per photo, peak bucket size is ~500 MB. That's nothing on Railway Pro.

The case the lifecycle rule would have handled — admin replaces a photo at an existing `public_id` — is rare on a closed alumni platform. When it happens with versioning off (Tigris), the new upload simply overwrites the old one in the bucket. We lose the old version, but Cloudinary's primary copy is intact and the system continues to work.

#### What to do instead — quarterly size check

Add a calendar reminder to run, every 90 days:

```bash
railway bucket info --bucket media-backup --json
```

Look at `storageBytes`. If it ever climbs into multi-GB territory unexpectedly, investigate why (rogue script? bug?) and consider manual cleanup via `aws s3 rm` or the Railway dashboard.

#### If you'd like to retry the lifecycle rule later

Two reasons it might become viable:

1. **Tigris adds versioning + non-current-expiration support.** Re-run `python scripts/apply_bucket_lifecycle.py` — the script and runbook walkthrough below are kept for that day.
2. **You move to a different S3-compatible backend** (e.g., a real B2 bucket, or AWS S3 directly). Same script works against any compliant S3 endpoint by changing the credentials.

Until either happens, the sections below are **historical reference**, not an operational procedure.

---

#### Reference (skip during normal provisioning) — one-shot Python script

```bash
python scripts/apply_bucket_lifecycle.py
```

Prerequisites: Railway CLI installed and authenticated (`railway whoami`), linked to the `Retrouvailles` project (`railway status`), and the project venv active so `boto3` is on the path.

The script is idempotent — safe to re-run. On success it prints the lifecycle config the backend echoed back so you can confirm it stuck. On Tigris-on-Railway it currently fails with the errors documented above; that is expected.

#### Reference — manual AWS CLI walkthrough

#### Step 0: install the AWS CLI (skip if you already have v2)

```bash
# macOS
brew install awscli

# Linux (Debian/Ubuntu)
sudo apt install awscli

# Windows (PowerShell)
winget install Amazon.AWSCLI

# verify
aws --version   # should print "aws-cli/2.x"
```

#### Step 1: pull bucket credentials and inspect the field names

```bash
railway bucket credentials --bucket media-backup --json
```

The JSON Railway currently returns:

```json
{
  "accessKeyId": "...",
  "bucketName": "media-backup",
  "endpoint": "https://t3.storageapi.dev",
  "region": "iad",
  "secretAccessKey": "...",
  "urlStyle": "..."
}
```

#### Step 2: export them as standard AWS env vars

**Bash / zsh** (macOS, Linux, Git Bash on Windows):

```bash
export AWS_ACCESS_KEY_ID=<accessKeyId from JSON>
export AWS_SECRET_ACCESS_KEY=<secretAccessKey from JSON>
export AWS_DEFAULT_REGION=<region from JSON>
ENDPOINT=<endpoint from JSON>
BUCKET=<bucketName from JSON>
```

**PowerShell** (Windows):

```powershell
$env:AWS_ACCESS_KEY_ID = "<accessKeyId from JSON>"
$env:AWS_SECRET_ACCESS_KEY = "<secretAccessKey from JSON>"
$env:AWS_DEFAULT_REGION = "<region from JSON>"
$ENDPOINT = "<endpoint from JSON>"
$BUCKET = "<bucketName from JSON>"
```

#### Step 3: enable versioning (precondition)

```bash
aws s3api put-bucket-versioning \
  --bucket "$BUCKET" \
  --endpoint-url "$ENDPOINT" \
  --versioning-configuration Status=Enabled
```

Verify:

```bash
aws s3api get-bucket-versioning --bucket "$BUCKET" --endpoint-url "$ENDPOINT"
# expected: { "Status": "Enabled" }
```

#### Step 4: write the lifecycle policy

```bash
cat > /tmp/lifecycle.json <<'EOF'
{
  "Rules": [
    {
      "ID": "rolling-90-day",
      "Status": "Enabled",
      "Filter": {"Prefix": ""},
      "NoncurrentVersionExpiration": {"NoncurrentDays": 90},
      "Expiration": {"ExpiredObjectDeleteMarker": true}
    }
  ]
}
EOF
```

What each field does:

- `Filter.Prefix=""` — applies to every object in the bucket.
- `NoncurrentVersionExpiration.NoncurrentDays=90` — once a version becomes "noncurrent" (because the same path was re-uploaded with new content), delete it after 90 days.
- `Expiration.ExpiredObjectDeleteMarker=true` — clean up tombstone delete markers when no other versions remain. Housekeeping.
- Notably: **no `Expiration.Days` rule.** Current versions live forever; backups are never auto-deleted by this rule.

#### Step 5: apply the policy

```bash
aws s3api put-bucket-lifecycle-configuration \
  --endpoint-url "$ENDPOINT" \
  --bucket "$BUCKET" \
  --lifecycle-configuration file:///tmp/lifecycle.json
```

Success is silent (no stdout, exit code 0).

#### Step 6: verify

```bash
aws s3api get-bucket-lifecycle-configuration --bucket "$BUCKET" --endpoint-url "$ENDPOINT"
```

Expected: the JSON from step 4 echoed back.

#### Troubleshooting

| Error | What it means | What to do |
|---|---|---|
| `NotImplemented` | Railway's S3 implementation doesn't support `put-bucket-lifecycle-configuration` yet | Skip §1.2; revisit when Railway adds support. Path-dedup keeps the bucket small at our scale. |
| `MalformedXML` | Same family of issue: Railway accepted the call but choked on the rule shape | Try a minimal rule first (just `NoncurrentVersionExpiration`, no `Expiration`); if still failing, skip §1.2. |
| `AccessDenied` on `put-bucket-versioning` | The bucket's app key doesn't have versioning permissions | Regenerate the bucket credentials in the Railway dashboard with broader scope, or apply the rule via Railway's web console if available. |
| `InvalidEndpoint` / connection refused | Wrong endpoint URL | Re-run `railway bucket credentials --bucket media-backup --json` and copy the value verbatim — the URL must include the `https://` scheme. |

### 1.3 Create the `media-backup-cron` Railway service

In the Railway dashboard, project `Retrouvailles`:

1. **+ New** → **Service** → **GitHub Repo** → connect `Bomino/lesretrouvailles`, branch `main`, root `/`. Use the existing Dockerfile.
2. Service settings:
   - **Service name**: `media-backup-cron`
   - **Settings → Build → Builder**: Dockerfile (auto-detected)
   - **Settings → Deploy → Start Command**: `python manage.py backup_media`
   - **Settings → Deploy → Cron Schedule**: `0 3 * * 0` (Sunday 03:00 UTC, per master spec §8.2)
3. Service variables (Settings → Variables) — use Railway's reference syntax to inherit from sibling services and the bucket:

   ```
   DATABASE_URL=${{ Postgres.DATABASE_URL }}
   SECRET_KEY=${{ lesretrouvailles.SECRET_KEY }}
   DJANGO_SETTINGS_MODULE=alumni.settings.staging
   ALLOWED_HOSTS=${{ lesretrouvailles.ALLOWED_HOSTS }}
   CLOUDINARY_CLIENT_PATH=${{ lesretrouvailles.CLOUDINARY_CLIENT_PATH }}
   CLOUDINARY_CLOUD_NAME=${{ lesretrouvailles.CLOUDINARY_CLOUD_NAME }}
   CLOUDINARY_API_KEY=${{ lesretrouvailles.CLOUDINARY_API_KEY }}
   CLOUDINARY_API_SECRET=${{ lesretrouvailles.CLOUDINARY_API_SECRET }}
   CLOUDINARY_URL=${{ lesretrouvailles.CLOUDINARY_URL }}
   BASIC_AUTH_REQUIRED=false
   SECURE_SSL_REDIRECT=false

   STORAGE_CLIENT_PATH=alumni.storage.RealStorage
   STORAGE_BACKUP_REQUIRED=true
   STORAGE_BUCKET_NAME=${{ media-backup.BUCKET_NAME }}
   STORAGE_ENDPOINT_URL=${{ media-backup.BUCKET_ENDPOINT }}
   STORAGE_ACCESS_KEY_ID=${{ media-backup.BUCKET_ACCESS_KEY_ID }}
   STORAGE_SECRET_ACCESS_KEY=${{ media-backup.BUCKET_SECRET_ACCESS_KEY }}
   STORAGE_REGION=auto
   ```

   The exact variable names exposed by the bucket may differ slightly; check `railway bucket credentials --bucket media-backup --json` to confirm and adjust the references on the right-hand side accordingly.

4. Click **Deploy** to push the first build.

### 1.4 First-run validation

1. Railway dashboard → `media-backup-cron` → click **Deploy** to trigger a one-off run (don't wait for Sunday).
2. Open the deployment logs. Expected:
   ```
   backup_media: 200 uploaded, 0 skipped, 0 failed (success rate 100.0%)
   ```
   (Number depends on current photo count — at ~200 members + a handful of memoires/memoriam, expect ~200–250 photos.)
3. List the bucket contents to confirm files land under `members/`, `memoires/`, `memoriam/`:
   ```bash
   aws s3 ls "s3://$BUCKET/" --endpoint-url "$ENDPOINT" --recursive | head
   ```
4. Confirm exit code = 0 (Railway shows the deployment as "Success").

### 1.5 Schedule the first restore drill

Calendar entry: 7 days after the first successful run, then every 90 days thereafter. See §4.

---

## 2. Verifying ongoing backups

To check that backups are still running healthily:

- **Railway dashboard** → `media-backup-cron` → **Deploys** → look at the most recent Sunday run. The log should show `backup_media: N uploaded, M skipped, 0 failed (success rate ≥95%)`.
- Or, list the bucket directly:
  ```bash
  aws s3 ls "s3://$BUCKET/" --endpoint-url "$ENDPOINT" --recursive | tail
  ```
  Recent timestamps (within the last 7 days) should appear on at least the newly added files.

---

## 3. Restoring a single photo

Use case: an admin or member asks for a photo that was deleted from Cloudinary by mistake, or the Cloudinary public_id was accidentally overwritten.

1. Find the photo's public_id in the database (search `Member`, `Memory`, or `InMemoriamEntry` by name or by `photo_public_id`).
2. Download the most recent bucket version:
   ```bash
   aws s3 cp "s3://$BUCKET/<public_id>" /tmp/restored-photo --endpoint-url "$ENDPOINT"
   ```
3. Sniff the format:
   ```bash
   file /tmp/restored-photo
   # -> /tmp/restored-photo: JPEG image data, ...
   ```
4. Re-upload to Cloudinary at the same public_id (keeps existing references valid):
   ```bash
   # cloudinary-cli: pip install cloudinary-cli
   cld uploader upload /tmp/restored-photo \
       public_id=<public_id> overwrite=true folder=<folder>
   ```
5. Verify the photo loads on the platform: hit the relevant member profile / memory detail / fiche page.

---

## 4. Quarterly restore drill

Cadence: first drill 7 days after the first successful backup, then every 90 days.

**Protocol:**

1. From the Django shell, pick a random photo:
   ```python
   import random
   from members.models import Member
   m = random.choice(list(Member.objects.exclude(photo_public_id="")))
   print(m.photo_public_id)
   ```
2. Restore that photo per §3 to a temp location (not back to Cloudinary):
   ```bash
   aws s3 cp "s3://$BUCKET/<public_id>" /tmp/drill-restored --endpoint-url "$ENDPOINT"
   ```
3. Fetch the live Cloudinary version for comparison:
   ```bash
   curl -o /tmp/drill-live https://res.cloudinary.com/daa3utt2i/image/upload/<public_id>
   ```
4. Compare:
   ```bash
   sha1sum /tmp/drill-restored /tmp/drill-live
   ```
   If the SHA1s differ but both are valid images: this is OK if Cloudinary applied a transformation on read. The restore validates that the file exists; visually inspect both to confirm they're the same photo.
5. Document the drill outcome (date + result) in a comment on the relevant phase issue, or append to a follow-up `docs/runbooks/drill-log.md`.

---

## 5. Cloudinary disaster scenario

If Cloudinary is unreachable for an extended period (acquisition, outage, account suspension):

1. **Confirm the scope.** Is it global Cloudinary down, our account suspended, or just one folder? Check status.cloudinary.com.
2. **Switch to read-from-bucket mode (manual)** — emergency procedure:
   - Provision a temporary host (Railway service or local) running Django + WhiteNoise.
   - Sync the bucket to that host's `/static/photos/` directory:
     ```bash
     aws s3 sync "s3://$BUCKET/" /tmp/photos/ --endpoint-url "$ENDPOINT"
     ```
   - Add a Django view that serves `/photos/<public_id>` from the synced files.
   - Update DNS or app code so `<cloud_name>.res.cloudinary.com` URLs resolve to the temp host.
3. **Restore later** — once Cloudinary is back, re-upload the most recent bucket version of each photo. The `backup_media` cron will then resume normally.

This procedure is intentionally manual. Building a built-in fallback view was deferred per the spec's non-goals.

---

## 6. Database restore

The platform's Postgres DB is on Railway with automatic daily snapshots (7-day retention).

**To restore:**

1. Railway dashboard → `Postgres` service → **Backups** tab.
2. Pick the most recent snapshot before the incident.
3. Click **Restore** → confirm.
4. Railway provisions a new database from the snapshot and updates `DATABASE_URL` automatically.

**Manual point-in-time export** (defense-in-depth, not required for P6a but available):

```bash
railway run --service Postgres -- pg_dump $DATABASE_URL | gzip > /tmp/db-$(date +%F).sql.gz
```

Store the resulting file in 1Password's encrypted file storage if you need to retain it longer than Railway's 7-day snapshot window.

---

## 7. Cost monitoring

- **Bucket storage**: ~12–24 GB peak at 90-day retention with current 200-member volume. Within the Pro plan's bucket allowance — negligible incremental cost.
- **Bucket egress**: backup uploads count as ingress (free). Restores or drill downloads count as egress; at our cadence (one quarterly drill, occasional single-photo restores) this stays within free tier territory.
- **Cron compute**: ~5 minutes per week of compute. Negligible.
- **Cloudinary**: backup downloads count as transformations. At ~250 photos × 52 weeks × 1 download each (path-dedup means only the delta after week 1) = ~250 downloads/year. Cloudinary free tier covers 25k transformations/month — well within margin.

If the bucket usage line in the Railway monthly bill ever exceeds expectations, check the lifecycle rule (§1.2) — old noncurrent versions should be expiring after 90 days. Revisit the rule via:

```bash
aws s3api get-bucket-lifecycle-configuration --bucket "$BUCKET" --endpoint-url "$ENDPOINT"
```
