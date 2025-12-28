#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
django.setup()

from dailyLedger.utils import parse_csv_ledger_entries, import_ledger_entries
from dailyLedger.models import Income

# Test CSV content for income
csv_content = '''Voucher_Number,Date,Amount,Major_Head,Head,Sub_Head,Payment_Type,Session,Details
V001,2024-01-15,50000,Fees,Monthly Fees,Class A,Cash,2023-2024,January fees collection
V002,2024-01-20,25000,BUF,Monthly BUF,Class B,Cash,2023-2024,January BUF collection
V003,2024-01-25,10000,Other Income,Donations,Library Fund,Cash,2023-2024,Library donation
V004,2024-02-15,45000,Fees,Monthly Fees,Class A,Cash,2023-2024,February fees collection'''

print("=" * 60)
print("Testing Income Bulk Import")
print("=" * 60)

# Parse the CSV
print("\n1. Parsing CSV...")
result = parse_csv_ledger_entries(csv_content, handle_duplicates='skip', ledger_type='Income')

print(f"\nValid rows: {len(result['valid_rows'])}")
if result['valid_rows']:
    for row_num, data in result['valid_rows']:
        print(f"  Row {row_num}: Voucher={data['voucher_number']}, Amount={data['amount']}, Major_Head={data['major_head']}")

print(f"\nErrors: {len(result['errors'])}")
for row_num, error in result['errors']:
    print(f"  Row {row_num}: {error}")

print(f"\nWarnings: {len(result['warnings'])}")
for row_num, warning in result['warnings']:
    print(f"  Row {row_num}: {warning}")

print(f"\nDuplicate rows: {len(result['duplicate_rows'])}")

# Import the data if no errors
if not result['errors']:
    print("\n2. Importing valid rows into database...")
    import_result = import_ledger_entries(
        result['valid_rows'],
        result['duplicate_rows'],
        handle_duplicates='skip',
        ledger_type='Income'
    )
    
    print(f"\nImport Results:")
    print(f"  Created: {import_result.get('created', 0)} records")
    print(f"  Updated: {import_result.get('updated', 0)} records")
    print(f"  Skipped: {import_result.get('skipped', 0)} records")
    
    if import_result.get('errors'):
        print(f"\nImport Errors:")
        for row_num, error in import_result['errors']:
            print(f"  Row {row_num}: {error}")
    
    # Verify in database
    print("\n3. Verifying in database...")
    income_count = Income.objects.count()
    print(f"Total Income records in database: {income_count}")
    
    # Show last few records
    recent = Income.objects.order_by('-id')[:4]
    print(f"\nLast {len(recent)} Income records:")
    for income in recent:
        print(f"  - {income.voucher_number}: {income.amount} ({income.major_head}/{income.head}) - {income.date}")

else:
    print("\n❌ Cannot import due to errors. Fix the CSV and try again.")

print("\n" + "=" * 60)
