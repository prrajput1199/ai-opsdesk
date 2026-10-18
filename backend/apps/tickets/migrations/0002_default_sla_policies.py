from django.db import migrations

DEFAULTS = {"URGENT": 4, "HIGH": 24, "MEDIUM": 72, "LOW": 120}


def create_policies(apps, schema_editor):
    SLAPolicy = apps.get_model("tickets", "SLAPolicy")
    for priority, hours in DEFAULTS.items():
        SLAPolicy.objects.get_or_create(priority=priority, defaults={"resolution_hours": hours})


class Migration(migrations.Migration):
    dependencies = [("tickets", "0001_initial")]
    operations = [migrations.RunPython(create_policies, migrations.RunPython.noop)]
