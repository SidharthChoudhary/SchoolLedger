# Generated migration to add payment_type column back to income table

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dailyLedger', '0022_remove_income_payment_type'),
    ]

    operations = [
        migrations.RunSQL(
            "ALTER TABLE dailyLedger_income ADD COLUMN payment_type VARCHAR(20) DEFAULT '' NULL;",
            reverse_sql="ALTER TABLE dailyLedger_income DROP COLUMN payment_type;",
        ),
    ]
