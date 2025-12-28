#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
django.setup()

from dailyLedger.utils import parse_csv_ledger_entries

csv_content = '''Voucher_Number,Date,Amount,Major_Head,Head,Sub_Head,Payment_Type,Session,Details
V001,2024-01-15,50000,Salary,Teacher,Poonam Gupta,Cash,2023-2024,Employee salary
V002,2024-01-20,5000,Operations,Books,ABC Book Publishers,Credit,2023-2024,Books purchase'''

result = parse_csv_ledger_entries(csv_content, handle_duplicates='skip', ledger_type='Expense')
print('Valid rows:', len(result['valid_rows']))
if result['valid_rows']:
    for row_num, data in result['valid_rows']:
        print(f"  Row {row_num}: {data}")
print('Errors:', result['errors'])
print('Warnings:', result['warnings'])
