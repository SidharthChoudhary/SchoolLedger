import os
os.chdir('c:\\LocalFolder\\SchoolLedger')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')

import django
django.setup()

from students.models import FeesAccount
from datetime import date

accounts = [
    {'account_name': 'Prep Class - 2025', 'account_open': date(2025, 1, 15), 'account_status': 'open'},
    {'account_name': 'Class 1 - 2025', 'account_open': date(2025, 1, 20), 'account_status': 'open'},
    {'account_name': 'Class 5 - 2024', 'account_open': date(2024, 1, 10), 'account_status': 'closed', 'account_close': date(2024, 12, 31)},
    {'account_name': 'Class 10 - 2025', 'account_open': date(2025, 2, 1), 'account_status': 'open'},
]

for i, acc in enumerate(accounts, 1):
    account = FeesAccount(
        account_name=acc['account_name'],
        account_open=acc['account_open'],
        account_status=acc['account_status'],
        account_close=acc.get('account_close')
    )
    account.save()
    print('Created: ' + account.account_id + ' - ' + account.account_name)

print(str(len(accounts)) + ' test fees accounts created!')
