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

### 1.2 Lifecycle (90-day rolling retention)

Railway buckets are S3-compatible and accept S3 lifecycle rules. From any host with the AWS CLI installed and the credentials above exported:

```bash
export AWS_ACCESS_KEY_ID=<BUCKET_ACCESS_KEY_ID>
export AWS_SECRET_ACCESS_KEY=<BUCKET_SECRET_ACCESS_KEY>
ENDPOINT=<BUCKET_ENDPOINT>
BUCKET=<BUCKET_NAME>

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

aws s3api put-bucket-lifecycle-configuration \
  --endpoint-url "$ENDPOINT" \
  --bucket "$BUCKET" \
  --lifecycle-configuration file:///tmp/lifecycle.json
```

Net effect: noncurrent versions expire after 90 days; current versions stay until overwritten or deleted.

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
