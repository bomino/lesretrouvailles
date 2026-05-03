"""Set the django.contrib.sites Site #1 to villageretrouvailles.com.

Django ships a default Site row with domain="example.com". The sitemap
framework reads this for <loc> URLs, so leaving it as example.com makes
/sitemap.xml advertise non-existent example.com URLs — broken for SEO.

This is a project-wide concern but lives in members/migrations because
core/ has no migrations of its own. The dependency on `sites.0002`
ensures the Site table exists before we update it.
"""

from __future__ import annotations

from django.db import migrations


CANONICAL_DOMAIN = "villageretrouvailles.com"
CANONICAL_NAME = "Les Retrouvailles — CEG 1 Birni"


def set_canonical_site(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    site, _ = Site.objects.update_or_create(
        pk=1,
        defaults={"domain": CANONICAL_DOMAIN, "name": CANONICAL_NAME},
    )


def revert_to_example(apps, schema_editor):
    Site = apps.get_model("sites", "Site")
    Site.objects.filter(pk=1).update(domain="example.com", name="example.com")


class Migration(migrations.Migration):

    dependencies = [
        ("members", "0006_publicsearchentry_and_more"),
        ("sites", "0002_alter_domain_unique"),
    ]

    operations = [
        migrations.RunPython(set_canonical_site, revert_to_example),
    ]
