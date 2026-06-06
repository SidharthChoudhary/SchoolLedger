"""
Management command: export_monthly_report

Generates a ZIP archive containing 4 CSV audit reports for a given month:
  - income_YYYY_MM.csv
  - expense_YYYY_MM.csv
  - payroll_YYYY_MM.csv
  - fees_summary_YYYY_MM.csv

Usage:
    python manage.py export_monthly_report --year 2026 --month 5
    python manage.py export_monthly_report --year 2026 --month 5 --output /path/to/dir

When called from the admin view the ZIP bytes are returned via stdout buffer.
"""

import csv
import io
import zipfile
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum, Count


class Command(BaseCommand):
    help = 'Export monthly audit reports (income, expense, payroll, fees) as a ZIP of CSVs'

    def add_arguments(self, parser):
        parser.add_argument('--year',  type=int, required=True, help='Year  (e.g. 2026)')
        parser.add_argument('--month', type=int, required=True, help='Month (1-12)')
        parser.add_argument(
            '--output', type=str, default='',
            help='Directory to write ZIP file. If omitted, writes to stdout as bytes.',
        )

    def handle(self, *args, **options):
        year  = options['year']
        month = options['month']

        if not (1 <= month <= 12):
            raise CommandError('Month must be between 1 and 12.')
        if year < 2000 or year > 2100:
            raise CommandError('Year looks invalid.')

        zip_bytes = build_monthly_zip(year, month)
        filename  = f'schoolledger_monthly_{year}_{month:02d}.zip'

        output_dir = options.get('output', '')
        if output_dir:
            import os
            path = os.path.join(output_dir, filename)
            with open(path, 'wb') as f:
                f.write(zip_bytes)
            self.stdout.write(self.style.SUCCESS(f'Saved: {path}'))
        else:
            # Write raw bytes to stdout buffer (used by the admin view)
            self.stdout.buffer.write(zip_bytes)


# ---------------------------------------------------------------------------
# Core export logic (importable from admin view)
# ---------------------------------------------------------------------------

def build_monthly_zip(year: int, month: int) -> bytes:
    """Build and return ZIP bytes containing all 4 monthly CSV reports."""
    label = f'{year}_{month:02d}'
    zip_buf = io.BytesIO()

    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f'income_{label}.csv',       _income_csv(year, month))
        zf.writestr(f'expense_{label}.csv',      _expense_csv(year, month))
        zf.writestr(f'payroll_{label}.csv',      _payroll_csv(year, month))
        zf.writestr(f'fees_summary_{label}.csv', _fees_summary_csv(year, month))

    return zip_buf.getvalue()


# ---------------------------------------------------------------------------
# Income CSV
# ---------------------------------------------------------------------------
def _income_csv(year: int, month: int) -> str:
    from dailyLedger.models import Income

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'Date', 'Voucher No', 'Session',
        'Major Head', 'Head', 'Sub Head',
        'Amount', 'Payment Type',
        'Fees Account ID', 'Fees Account Name',
        'Details',
    ])

    qs = (
        Income.objects
        .filter(date__year=year, date__month=month)
        .select_related('session', 'fees_account')
        .order_by('date', 'id')
    )

    for entry in qs:
        writer.writerow([
            entry.date,
            entry.voucher_number,
            entry.session.session if entry.session else '',
            entry.major_head,
            entry.head,
            entry.sub_head,
            entry.amount,
            entry.payment_type,
            entry.fees_account.account_id if entry.fees_account else '',
            entry.fees_account.name       if entry.fees_account else '',
            entry.details,
        ])

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Expense CSV
# ---------------------------------------------------------------------------
def _expense_csv(year: int, month: int) -> str:
    from dailyLedger.models import Expense

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'Date', 'Voucher No', 'Session',
        'Major Head', 'Head', 'Sub Head',
        'Amount', 'Payment Type',
        'Employee No', 'Employee Name',
        'Details',
    ])

    qs = (
        Expense.objects
        .filter(date__year=year, date__month=month)
        .select_related('session', 'employee')
        .order_by('date', 'id')
    )

    for entry in qs:
        writer.writerow([
            entry.date,
            entry.voucher_number,
            entry.session.session if entry.session else '',
            entry.major_head,
            entry.head,
            entry.sub_head,
            entry.amount,
            entry.payment_type,
            entry.employee.emp_no   if entry.employee else '',
            entry.employee.name     if entry.employee else '',
            entry.details,
        ])

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Payroll CSV
# ---------------------------------------------------------------------------
def _payroll_csv(year: int, month: int) -> str:
    from employees.models import EmployeePayrollEntry

    month_str = f'{year}-{month:02d}'
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'Employee No', 'Employee Name', 'Post',
        'Session', 'Month',
        'Base Salary', 'Payable Salary',
        'Old Dues', 'Other Amount', 'Total Payable',
        'Note',
    ])

    qs = (
        EmployeePayrollEntry.objects
        .filter(month=month_str)
        .select_related('employee', 'session')
        .order_by('employee__name')
    )

    for entry in qs:
        total = (entry.payable_salary or 0) + entry.old_dues + entry.other_amount
        writer.writerow([
            entry.employee.emp_no,
            entry.employee.name,
            entry.employee.post,
            entry.session.session if entry.session else '',
            entry.month,
            entry.employee.base_salary_per_month,
            entry.payable_salary if entry.payable_salary is not None else '',
            entry.old_dues,
            entry.other_amount,
            total,
            entry.note,
        ])

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Fees summary CSV  (income grouped by fees account for the month)
# ---------------------------------------------------------------------------
def _fees_summary_csv(year: int, month: int) -> str:
    from dailyLedger.models import Income

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'Fees Account ID', 'Fees Account Name',
        'No. of Payments', 'Total Collected (Rs)',
    ])

    # Accounts that had at least one income entry this month
    qs = (
        Income.objects
        .filter(date__year=year, date__month=month, fees_account__isnull=False)
        .values(
            'fees_account__account_id',
            'fees_account__name',
        )
        .annotate(
            payment_count=Count('id'),
            total=Sum('amount'),
        )
        .order_by('fees_account__account_id')
    )

    for row in qs:
        writer.writerow([
            row['fees_account__account_id'],
            row['fees_account__name'],
            row['payment_count'],
            row['total'],
        ])

    # Summary row
    totals = Income.objects.filter(
        date__year=year, date__month=month, fees_account__isnull=False
    ).aggregate(total=Sum('amount'), count=Count('id'))
    writer.writerow([])
    writer.writerow([
        'TOTAL', '',
        totals['count'] or 0,
        totals['total'] or 0,
    ])

    return buf.getvalue()
