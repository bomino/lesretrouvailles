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
GHOST_STALE_REMOVED_REASON = "Périmée — non renouvelée par les admins"


class Command(BaseCommand):
    help = "Daily processor for cooptation deadlines (J+7, J+14, retention purge)."

    def handle(self, *args, **opts):
        now = timezone.now()
        sent_reminders = self._send_j7_reminders(now)
        expired_apps = self._expire_j14(now)
        stale_apps = self._sweep_stale_questionnaires(now)
        ghosts_purged = self._purge_stale_ghosts(now)
        digest_sent = 0
        if now.day == 1 and now.month in GHOST_DIGEST_QUARTERLY_MONTHS:
            digest_sent = self._send_quarterly_ghost_digest(now)
        purged_apps = self._purge_old_rejections(now)
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. reminders={sent_reminders} expired={expired_apps} "
                f"stale={stale_apps} ghosts_purged={ghosts_purged} "
                f"digest_sent={digest_sent} purged={purged_apps}"
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
            emails.send_parrain_reminder(req)
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
                app.cooptation_outcome = "expired"
                if not app.questionnaire_token:
                    app.questionnaire_token = secrets.token_urlsafe(32)
                app.cooptation_expired_at = now
                app.save()
                site_url = getattr(settings, "SITE_URL", "https://staging.villageretrouvailles.com")
                qurl = f"{site_url}/questionnaire/{app.questionnaire_token}/"
                emails.send_cooptation_expired(app, questionnaire_url=qurl)
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
        return len(purged)

    def _purge_old_rejections(self, now) -> int:
        qs = AdminApplication.objects.filter(status="rejected", retention_until__lte=now)
        count = 0
        for app in qs:
            services.purge_application(app)
            count += 1
        return count
