from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0008_feesaccountlegacybalance'),
    ]

    operations = [
        migrations.AddField(
            model_name='feesaccountagreement',
            name='opening_balance',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.DeleteModel(
            name='FeesAccountLegacyBalance',
        ),
    ]
