"""Signal handlers for the membership app."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Member, NotificationPreference


@receiver(post_save, sender=Member)
def create_preferences_for_new_member(sender, instance, created, **kwargs):
    if created:
        NotificationPreference.objects.create(member=instance)
