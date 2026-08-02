"""Daily idempotent cron.

Cooptation handlers (P3): J+7 reminders, J+14 expiry transitions,
stale-questionnaire sweep, 6-month retention purge.

Cross-app housekeeping (P4c): stale-ghost auto-removal, quarterly
admin digest. The 'process_cooptation_deadlines' name is historical;
keeping the existing cron service running this single command is
cheaper than splitting into two services for our scale.

Run via Railway cron service; sharing the app's image and env."""

from __future__ import annotations

import secrets
import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.utils import timezone

from cooptation import emails, services
from cooptation.models import AdminApplication, CooptationRequest

# Cross-app: P4c housekeeping operates on members.PublicSearchEntry.
from members import emails as members_emails
from members.models import AuditLog, PublicSearchEntry

PACING_SECONDS = 0.5
# After both parrains time out and we email the questionnaire link, give the
# candidate this many days to submit it. After that, push the application to
# awaiting_admin so the admin can decide manually instead of letting it rot
# in cooptation_pending forever.
QUESTIONNAIRE_GRACE_DAYS = 7

# P4c: ghost-list governance constants.
GHOST_STALE_THRESHOLD_DAYS = 365
GHOST_DIGEST_LOOKBACK_DAYS = 90
GHOST_DIGEST_QUARTERLY_MONTHS = (1, 4, 7, 10)
# Fire window inside a quarter month: any run on days 1-7 sends the digest
# once (guarded by the ghost.digest.sent AuditLog marker).
GHOST_DIGEST_WINDOW_DAYS = 7
GHOST_STALE_REMOVED_REASON = "Périmée — non renouvelée par les admins"

# Applications the admin never decided keep full PII in awaiting_admin; align
# their retention with the 180 days rejected candidates already get.
UNDECIDED_RETENTION_DAYS = 180

# P6c: AuditLog retention. Master spec §9.4 — "Logs d'audit : Conservés 12 mois
# pour sécurité/légal puis purgés." Applies uniformly across all action types
# (including rgpd.member.purged itself). If a future compliance need requires
# keeping a subset longer, filter by action in a follow-up phase.
AUDIT_LOG_RETENTION_DAYS = 365

# RemovalRequest holds the requester's email, IP, free-text reason and a live
# confirm token. Once the request is settled (confirmed or expired) that data is
# spent — it identifies a person who asked to be *removed* from a public list, so
# keeping it forever is the opposite of the point. Pending requests are left
# alone: they are still actionable by the person who made them.
REMOVAL_REQUEST_RETENTION_DAYS = 180


class Command(BaseCommand):
    help = "Daily processor for cooptation deadlines (J+7, J+14, retention purge)."

    def handle(self, *args, **opts):
        now = timezone.now()
        sent_reminders = self._send_j7_reminders(now)
        expired_apps = self._expire_j14(now)
        stale_apps = self._sweep_stale_questionnaires(now)
        ghosts_purged = self._purge_stale_ghosts(now)
        digest_sent = 0
        # Days 1-7 (not `day == 1`): a cron missed on the 1st used to skip a
        # whole quarter. The ghost.digest.sent marker makes the window
        # idempotent — one digest per quarter month, however many runs land
        # inside it.
        if now.month in GHOST_DIGEST_QUARTERLY_MONTHS and now.day <= GHOST_DIGEST_WINDOW_DAYS:
            already_sent = AuditLog.objects.filter(
                action="ghost.digest.sent",
                created_at__year=now.year,
                created_at__month=now.month,
            ).exists()
            if not already_sent:
                digest_sent = self._send_quarterly_ghost_digest(now)
        purged_apps = self._purge_old_rejections(now)
        purged_undecided = self._purge_stale_undecided(now)
        purged_audit = self._purge_old_audit_logs(now)
        purged_removals = self._purge_old_removal_requests(now)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. reminders={sent_reminders} expired={expired_apps} "
                f"stale={stale_apps} ghosts_purged={ghosts_purged} "
                f"digest_sent={digest_sent} purged={purged_apps} "
                f"undecided_purged={purged_undecided} "
                f"audit_purged={purged_audit} removals_purged={purged_removals}"
            )
        )

    def _send_j7_reminders(self, now) -> int:
        """For each pending CooptationRequest where now is within 7 days of expires_at
        and no reminder has been sent, send one and stamp reminder_sent_at."""
        threshold_low = now
        threshold_high = now + timedelta(days=7)
        qs = CooptationRequest.objects.filter(
            response="pending",
            reminder_sent_at__isnull=True,
            expires_at__gt=threshold_low,
            expires_at__lte=threshold_high,
        )
        count = 0
        for req in qs:
            # Same per-item isolation as _expire_j14's sends: one Resend
            # failure must not raise out of handle() — everything after this
            # stage (J+14 expiry, retention purges) would silently be skipped
            # for the day. The send happens BEFORE the stamp on purpose: a
            # failed send leaves reminder_sent_at NULL, so the reminder is
            # retried on the next run instead of being permanently skipped.
            try:
                emails.send_parrain_reminder(req)
            except Exception as e:  # noqa: BLE001
                self.stderr.write(f"  ERROR reminder req={req.pk}: {e}")
                continue
            req.reminder_sent_at = now
            req.save()
            count += 1
            time.sleep(PACING_SECONDS)
        return count

    def _expire_j14(self, now) -> int:
        """For each AdminApplication in cooptation_pending whose all requests are
        either non-pending or past expires_at, transition to awaiting_admin (or
        questionnaire fallback via questionnaire_token if any timed out)."""
        apps = AdminApplication.objects.filter(status="cooptation_pending").distinct()
        count = 0
        for app in apps:
            requests = list(app.cooptation_requests.all())
            still_open = [r for r in requests if r.response == "pending" and r.expires_at > now]
            if still_open:
                continue
            timed_out = [r for r in requests if r.response == "pending" and r.expires_at <= now]
            if timed_out:
                # At least one expired without a response — fallback to
                # questionnaire. Skip if we've already sent the email on a
                # previous run, otherwise the candidate gets a duplicate
                # every day until they submit.
                if app.cooptation_expired_at is not None:
                    continue
                # Persist outcome + token BEFORE the send so the emailed URL
                # resolves; stamp cooptation_expired_at only AFTER a
                # successful send. A failed send leaves expired_at None, so
                # the app is retried on the next run instead of being
                # permanently skipped, and one outage doesn't abort the run.
                app.cooptation_outcome = "expired"
                if not app.questionnaire_token:
                    app.questionnaire_token = secrets.token_urlsafe(32)
                app.save()
                site_url = getattr(settings, "SITE_URL", "https://staging.villageretrouvailles.com")
                qurl = f"{site_url}/questionnaire/{app.questionnaire_token}/"
                try:
                    emails.send_cooptation_expired(app, questionnaire_url=qurl)
                except Exception as e:  # noqa: BLE001
                    self.stderr.write(f"  ERROR expired-email app={app.pk}: {e}")
                    continue
                app.cooptation_expired_at = now
                app.save()
                count += 1
                time.sleep(PACING_SECONDS)
            else:
                # All responded — derive outcome and move to awaiting_admin
                app.cooptation_outcome = self._derive_outcome(requests)
                app.status = "awaiting_admin"
                app.save()
                count += 1
        return count

    def _sweep_stale_questionnaires(self, now) -> int:
        """Push to awaiting_admin any application whose cooptation expired,
        the candidate was emailed the questionnaire, and they never submitted
        within the grace window. Without this sweep the application sits
        in cooptation_pending indefinitely (admin sees nothing actionable)."""
        cutoff = now - timedelta(days=QUESTIONNAIRE_GRACE_DAYS)
        qs = AdminApplication.objects.filter(
            status="cooptation_pending",
            cooptation_outcome="expired",
            cooptation_expired_at__lte=cutoff,
            questionnaire_responses__isnull=True,
        ).distinct()
        count = 0
        for app in qs:
            app.status = "awaiting_admin"
            app.save()
            count += 1
        return count

    @staticmethod
    def _derive_outcome(requests) -> str:
        responses = [r.response for r in requests]
        if not responses:
            # Zero CooptationRequest rows (deleted via /admin/): all() over an
            # empty list is True, which used to mislabel this "all_accepted".
            return "pending"
        if all(r == "accepted" for r in responses):
            return "all_accepted"
        if all(r == "refused" for r in responses):
            return "all_refused"
        return "mixed"

    def _purge_stale_ghosts(self, now) -> int:
        """Auto-remove published ghost entries (1+ cosigner) older than 12 months.

        'Published' = 1+ admin signoff (P4d single-admin governance). 'Stale'
        = added_at <= now - 365 days AND removed_at IS NULL. Removal is
        recorded via AuditLog (ghost.entry.purged) and the entry's removed_at
        + removed_reason are set so the existing public queryset filters it out
        automatically.
        """
        cutoff = now - timedelta(days=GHOST_STALE_THRESHOLD_DAYS)
        candidates = (
            PublicSearchEntry.objects.filter(removed_at__isnull=True, added_at__lte=cutoff)
            .annotate(n=Count("added_by_admins"))
            .filter(n__gte=1)
        )
        count = 0
        for entry in candidates:
            entry.removed_at = now
            entry.removed_reason = GHOST_STALE_REMOVED_REASON
            entry.save(update_fields=["removed_at", "removed_reason"])
            AuditLog.objects.create(
                actor=None,
                action="ghost.entry.purged",
                target_type="members.PublicSearchEntry",
                target_id=str(entry.pk),
                metadata={
                    "first_name": entry.first_name,
                    "last_name_initial": entry.last_name_initial,
                    "added_at": entry.added_at.date().isoformat(),
                    "auto_removed_at": now.date().isoformat(),
                },
            )
            count += 1
        return count

    def _send_quarterly_ghost_digest(self, now) -> int:
        """Once on day 1 of Jan/Apr/Jul/Oct: email staff a digest of every
        ghost.entry.purged AuditLog entry from the last 90 days, plus a
        snapshot of currently-listed entries with their age in months.

        No-op if zero entries were auto-removed in that window.
        """
        since = now - timedelta(days=GHOST_DIGEST_LOOKBACK_DAYS)
        purged = list(
            AuditLog.objects.filter(action="ghost.entry.purged", created_at__gte=since).order_by(
                "-created_at"
            )
        )
        if not purged:
            return 0

        currently_listed = list(
            PublicSearchEntry.objects.filter(removed_at__isnull=True)
            .annotate(n=Count("added_by_admins"))
            .filter(n__gte=1)
            .order_by("added_at")
        )
        for e in currently_listed:
            e.age_months = round((now - e.added_at).days / 30)

        members_emails.send_admin_quarterly_ghost_digest(
            purged_logs=purged,
            currently_listed=currently_listed,
            since=since,
        )
        # The sent marker handle() checks before firing again this month.
        # Written only after a successful send, so a failed send retries on
        # the next run inside the window.
        AuditLog.objects.create(
            actor=None,
            action="ghost.digest.sent",
            target_type="members.PublicSearchEntry",
            target_id="",
            metadata={
                "purged_count": len(purged),
                "listed_count": len(currently_listed),
                "window_start": since.date().isoformat(),
            },
        )
        return len(purged)

    def _purge_old_rejections(self, now) -> int:
        qs = AdminApplication.objects.filter(status="rejected", retention_until__lte=now)
        count = 0
        for app in qs:
            services.purge_application(app)
            count += 1
        return count

    def _purge_stale_undecided(self, now) -> int:
        """Purge applications stuck in awaiting_admin past the retention window.

        retention_until is only ever set on rejection, so an application the
        admin never decided kept full PII (name, email, WhatsApp, IP)
        indefinitely — while a *rejected* candidate's data was erased after
        180 days. An undecided candidate must not be retained longer than a
        refused one. 180 days of admin inaction is a de-facto refusal; the
        candidate can always reapply.
        """
        cutoff = now - timedelta(days=UNDECIDED_RETENTION_DAYS)
        qs = AdminApplication.objects.filter(status="awaiting_admin", submitted_at__lte=cutoff)
        count = 0
        for app in qs:
            services.purge_application(app)
            count += 1
        return count

    def _purge_old_removal_requests(self, now) -> int:
        """Delete settled ghost-removal requests past the retention window.

        These rows carry requester_email, requester_ip, a free-text reason and a
        confirm token. Nothing purged them before — the audit-log purge covered
        AuditLog only. Pending requests are untouched: someone may still click
        their confirmation link.
        """
        from members.models import RemovalRequest

        cutoff = now - timedelta(days=REMOVAL_REQUEST_RETENTION_DAYS)
        deleted, _ = RemovalRequest.objects.filter(
            status__in=("confirmed", "expired"),
            requested_at__lt=cutoff,
        ).delete()
        return deleted

    def _purge_old_audit_logs(self, now) -> int:
        """Delete AuditLog entries older than AUDIT_LOG_RETENTION_DAYS.

        Master spec §9.4: "Logs d'audit : Conservés 12 mois pour sécurité/légal
        puis purgés." Empty queryset is a no-op; idempotent across runs.
        """
        from members.models import AuditLog

        cutoff = now - timedelta(days=AUDIT_LOG_RETENTION_DAYS)
        deleted, _ = AuditLog.objects.filter(created_at__lt=cutoff).delete()
        return deleted
