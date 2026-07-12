"""F-02: make contact visibility opt-IN, and fix the rows created under the old default.

`show_email` / `show_whatsapp` defaulted to True, while guide_membre.md and
aide/faq.py have always told members they are "décoché par défaut". The launch
import creates ~200 members straight from the WhatsApp roster, so every one of
them would have published their phone number to the whole directory on day one —
having been told the opposite.

The data pass is deliberately lossy: because the old default was True, a True
value cannot be distinguished from "I chose to publish", so we hide everyone and
let them re-enable it in one click (Profil → Modifier). Hiding someone who wanted
to be visible is an annoyance; publishing someone who was promised privacy is a
breach. The reverse is a no-op — see _helpers.noop_reverse.

`show_city` is untouched: the docs promise that one IS checked by default.
"""

from django.db import migrations, models

from ._helpers import hide_contact_by_default, noop_reverse


class Migration(migrations.Migration):
    dependencies = [
        ("members", "0022_alter_auditlog_action_classrosterentry"),
    ]

    operations = [
        migrations.AlterField(
            model_name="member",
            name="show_email",
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name="member",
            name="show_whatsapp",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(hide_contact_by_default, noop_reverse),
    ]
