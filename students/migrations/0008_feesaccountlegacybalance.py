from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dailyLedger', '0005_feesstructure_uniform_hoody_and_more'),
        ('students', '0007_add_remark_to_feesaccount'),
    ]

    operations = [
        migrations.CreateModel(
            name='FeesAccountLegacyBalance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('balance_fee', models.DecimalField(decimal_places=2, max_digits=12)),
                ('note', models.CharField(blank=True, max_length=255, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('fees_account', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='legacy_balances', to='students.feesaccount')),
                ('session', models.ForeignKey(on_delete=models.deletion.CASCADE, related_name='fees_account_legacy_balances', to='dailyLedger.session')),
            ],
            options={
                'verbose_name': 'Fees Account Legacy Balance',
                'verbose_name_plural': 'Fees Account Legacy Balances',
                'ordering': ['-session', 'fees_account__account_id'],
                'unique_together': {('session', 'fees_account')},
            },
        ),
    ]
