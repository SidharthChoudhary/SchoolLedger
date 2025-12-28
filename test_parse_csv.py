#!/usr/bin/env python
import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
sys.path.insert(0, '/workspace')
django.setup()

from dailyLedger.utils import parse_csv_ledger_entries
from datetime import datetime

# Read the test CSV file
with open('test_ledger_import.csv', 'r', encoding='utf-8') as f:
    csv_content = f.read()

# Parse the CSV
print("Parsing CSV file...")
result = parse_csv_ledger_entries(csv_content, handle_duplicates='skip', ledger_type='Expense')

print(f"\n{'='*60}")
print("PARSING RESULTS")
print(f"{'='*60}")
print(f"Valid rows: {len(result['valid_rows'])}")
print(f"Duplicate rows: {len(result['duplicate_rows'])}")
print(f"Errors: {len(result['errors'])}")
print(f"Warnings: {len(result['warnings'])}")

if result['errors']:
    print(f"\n{'='*60}")
    print("ERRORS (First 10)")
    print(f"{'='*60}")
    for row_num, error_msg in result['errors'][:10]:
        print(f"Row {row_num}: {error_msg}")

if result['warnings']:
    print(f"\n{'='*60}")
    print("WARNINGS (First 10)")
    print(f"{'='*60}")
    for row_num, warning_msg in result['warnings'][:10]:
        print(f"Row {row_num}: {warning_msg}")

if result['valid_rows']:
    print(f"\n{'='*60}")
    print("SAMPLE VALID ROWS (First 5)")
    print(f"{'='*60}")
    for row_num, data in result['valid_rows'][:5]:
        print(f"\nRow {row_num}:")
        print(f"  Voucher: {data['voucher_number']}")
        print(f"  Date: {data['date']}")
        print(f"  Amount: {data['amount']}")
        print(f"  Account Type: {data['account_type']}")
        print(f"  Account Name: {data['account_name']}")
        print(f"  Head: {data['major_head']}/{data['head']}/{data['sub_head']}")
        print(f"  Payment Type: {data['payment_type']}")
        print(f"  Ledger Type: {data['ledger_type']}")
        print(f"  Session: {data['session_id']}")

if result['duplicate_rows']:
    print(f"\n{'='*60}")
    print("DUPLICATE ROWS (First 5)")
    print(f"{'='*60}")
    for row_num, data in result['duplicate_rows'][:5]:
        print(f"Row {row_num}: {data['voucher_number']} - {data['amount']}")
