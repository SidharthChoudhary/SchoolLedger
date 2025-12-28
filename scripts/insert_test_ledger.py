import os
import django
from datetime import date, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
django.setup()

from dailyLedger.models import Expense, Head, Session

# Test ledger entries data
ledger_data = [
    {
        'voucher_number': 'EXP/001',
        'date': date.today() - timedelta(days=10),
        'amount': 5000.00,
        'details': 'Electricity bill for December',
        'account_name': 'School Account',
        'major_head': 'Administrative',
        'head': 'Utilities',
        'sub_head': 'Electricity',
        'ledger_type': 'Expense',
        'payment_type': 'Cash',
    },
    {
        'voucher_number': 'EXP/002',
        'date': date.today() - timedelta(days=8),
        'amount': 12000.00,
        'details': 'Monthly teacher salary - December',
        'account_name': 'School Account',
        'major_head': 'Staff',
        'head': 'Salaries',
        'sub_head': 'Teaching Staff',
        'ledger_type': 'Expense',
        'payment_type': 'Credit',
    },
    {
        'voucher_number': 'INC/001',
        'date': date.today() - timedelta(days=5),
        'amount': 25000.00,
        'details': 'Student fees - December batch 1',
        'account_name': 'Fees Account',
        'major_head': 'Revenue',
        'head': 'Fees',
        'sub_head': 'Tuition Fees',
        'ledger_type': 'Income',
        'payment_type': 'Cash',
    },
    {
        'voucher_number': 'EXP/003',
        'date': date.today() - timedelta(days=3),
        'amount': 3500.00,
        'details': 'Stationery supplies purchase',
        'account_name': 'School Account',
        'major_head': 'Supplies',
        'head': 'Office Supplies',
        'sub_head': 'Stationery',
        'ledger_type': 'Expense',
        'payment_type': 'Cash',
    },
    {
        'voucher_number': 'EXP/004',
        'date': date.today() - timedelta(days=1),
        'amount': 8000.00,
        'details': 'Maintenance - Building repairs',
        'account_name': 'School Account',
        'major_head': 'Maintenance',
        'head': 'Building',
        'sub_head': 'Repairs',
        'ledger_type': 'Expense',
        'payment_type': 'Credit',
    },
    {
        'voucher_number': 'INC/002',
        'date': date.today(),
        'amount': 18000.00,
        'details': 'Student fees - December batch 2',
        'account_name': 'Fees Account',
        'major_head': 'Revenue',
        'head': 'Fees',
        'sub_head': 'Tuition Fees',
        'ledger_type': 'Income',
        'payment_type': 'Cash',
    },
]

# Get the first active session (or create one if needed)
try:
    session = Session.objects.filter(status='Active').first()
    if not session:
        session = Session.objects.first()  # fallback to any session
except:
    session = None

# Insert ledger entries
count = 0
for entry in ledger_data:
    entry['session'] = session
    expense, created = Expense.objects.get_or_create(
        voucher_number=entry['voucher_number'],
        date=entry['date'],
        defaults={
            'amount': entry['amount'],
            'details': entry['details'],
            'account_name': entry['account_name'],
            'major_head': entry['major_head'],
            'head': entry['head'],
            'sub_head': entry['sub_head'],
            'ledger_type': entry['ledger_type'],
            'payment_type': entry['payment_type'],
            'session': session,
        }
    )
    if created:
        print(f'✓ Created: {entry["voucher_number"]} - {entry["details"]} (₹{entry["amount"]})')
        count += 1
    else:
        print(f'- Already exists: {entry["voucher_number"]}')

print(f'\n{count} test ledger entries inserted successfully!')
