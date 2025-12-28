#!/usr/bin/env python
import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
sys.path.insert(0, '/workspace')
django.setup()

from dailyLedger.utils import parse_csv_ledger_entries

# Read the test CSV file
with open('test_new_account_types.csv', 'r', encoding='utf-8') as f:
    csv_content = f.read()

# Parse as Expense
print("=" * 70)
print("PARSING EXPENSE ENTRIES")
print("=" * 70)
result_expense = parse_csv_ledger_entries(csv_content, handle_duplicates='skip', ledger_type='Expense')

print(f"Valid rows: {len(result_expense['valid_rows'])}")
print(f"Errors: {len(result_expense['errors'])}")

if result_expense['errors']:
    print("\nErrors:")
    for row_num, error_msg in result_expense['errors']:
        print(f"  Row {row_num}: {error_msg}")

if result_expense['valid_rows']:
    print("\nValid Rows:")
    for row_num, data in result_expense['valid_rows']:
        print(f"\nRow {row_num}: {data['voucher_number']}")
        print(f"  Account: {data['account_name']} ({data['account_type']})")
        print(f"  Amount: {data['amount']}")
        print(f"  Head: {data['major_head']}/{data['head']}/{data['sub_head']}")
        print(f"  Type: {data['ledger_type']}")

# Parse as Income  
print("\n" + "=" * 70)
print("PARSING INCOME ENTRIES")
print("=" * 70)
result_income = parse_csv_ledger_entries(csv_content, handle_duplicates='skip', ledger_type='Income')

print(f"Valid rows: {len(result_income['valid_rows'])}")
print(f"Errors: {len(result_income['errors'])}")

if result_income['errors']:
    print("\nErrors:")
    for row_num, error_msg in result_income['errors']:
        print(f"  Row {row_num}: {error_msg}")
