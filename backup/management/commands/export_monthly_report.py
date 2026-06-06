"""
Management command: export_monthly_report

Generates a ZIP archive containing 4 CSV audit reports for a given
academic session (April→March) or a specific month within a session.

Usage:
    # Specific month within a session
    python manage.py export_monthly_report --session 2025-2026 --month 4

    # All months in a session (April → March)
    python manage.py export_monthly_report --session 2025-2026 --month 0

    # Write to a directory instead of stdout
    python manage.py export_monthly_report --session 2025-2026 --month 0 --output /path/to/dir
"""

import calendar
import csv
import io
import zipfile
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Sum, Count


MONTH_NAMES = {
    1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr',
    5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug',
    9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec',
}

# Academic year month order: April first
ACADEMIC_MONTHS = [4, 5, 6, 7, 8, 9, 10, 11, 12, 1, 2, 3]


class Command(BaseCommand):
    help = 'Export monthly audit reports as CSV ZIP for a given academic session'

    def add_arguments(self, parser):
        parser.add_argument(
            '--session', type=str, required=True,
            help='Academic session string, e.g. 2025-2026',
        )
        parser.add_argument(
            '--month', type=int, default=0,
            help='Month 1-12, or 0 for all months in the session (default: 0)',
        )
        parser.add_argument(
            '--output', type=str, default='',
            help='Directory to write ZIP. If omitted, writes bytes to stdout.',
        )

    def handle(self, *args, **options):
        session_str = options['session']
        month       = options['month']

        if not _valid_session(session_str):
            raise CommandError(
                f'Invalid session format: "{session_str}". Expected e.g. 2025-2026'
            )
        if not (0 <= month <= 12):
            raise CommandError('Month must be 0 (all) or 1-12.')

        if month == 0:
            zip_bytes = build_session_zip(session_str)
            filename  = f'schoolledger_{session_str}_all_months.zip'
        else:
            zip_bytes = build_month_zip(session_str, month)
            filename  = f'schoolledger_{session_str}_{month:02d}_{MONTH_NAMES[month]}.zip'

        output_dir = options.get('output', '')
        if output_dir:
            import os
            path = os.path.join(output_dir, filename)
            with open(path, 'wb') as f:
                f.write(zip_bytes)
            self.stdout.write(self.style.SUCCESS(f'Saved: {path}'))
        else:
            self.stdout.buffer.write(zip_bytes)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_session(session_str: str) -> bool:
    """Validate format '2025-2026'."""
    try:
        parts = session_str.split('-')
        return len(parts) == 2 and int(parts[0]) + 1 == int(parts[1])
    except (ValueError, AttributeError):
        return False


def _session_years(session_str: str):
    """'2025-2026' → (2025, 2026)"""
    parts = session_str.split('-')
    return int(parts[0]), int(parts[1])


def _date_range_for_session(session_str: str):
    """Return (start_date, end_date) covering April Y1 → 31 March Y2."""
    y1, y2 = _session_years(session_str)
    return date(y1, 4, 1), date(y2, 3, 31)


def _year_for_month(session_str: str, month: int) -> int:
    """Return the calendar year for a given academic month within a session."""
    y1, y2 = _session_years(session_str)
    return y1 if month >= 4 else y2


def _payroll_months_for_session(session_str: str):
    """Return all YYYY-MM strings for the full academic session."""
    y1, y2 = _session_years(session_str)
    months = []
    for m in range(4, 13):
        months.append(f'{y1}-{m:02d}')
    for m in range(1, 4):
        months.append(f'{y2}-{m:02d}')
    return months


# ---------------------------------------------------------------------------
# Public ZIP builders (called from admin view too)
# ---------------------------------------------------------------------------

def build_session_zip(session_str: str) -> bytes:
    """Full academic session export (April → March)."""
    label   = session_str
    zip_buf = io.BytesIO()
    start, end = _date_range_for_session(session_str)

    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f'income_{label}.csv',
                    _income_csv_range(start, end))
        zf.writestr(f'expense_{label}.csv',
                    _expense_csv_range(start, end))
        zf.writestr(f'payroll_{label}.csv',
                    _payroll_csv_months(_payroll_months_for_session(session_str)))
        zf.writestr(f'fees_summary_{label}.csv',
                    _fees_summary_csv_range(start, end))

    return zip_buf.getvalue()


def build_month_zip(session_str: str, month: int) -> bytes:
    """Single-month export within an academic session."""
    year  = _year_for_month(session_str, month)
    label = f'{session_str}_{month:02d}_{MONTH_NAMES[month]}'
    start = date(year, month, 1)
    end   = date(year, month, calendar.monthrange(year, month)[1])

    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f'income_{label}.csv',
                    _income_csv_range(start, end))
        zf.writestr(f'expense_{label}.csv',
                    _expense_csv_range(start, end))
        zf.writestr(f'payroll_{label}.csv',
                    _payroll_csv_months([f'{year}-{month:02d}']))
        zf.writestr(f'fees_summary_{label}.csv',
                    _fees_summary_csv_range(start, end))

    return zip_buf.getvalue()


# ---------------------------------------------------------------------------
# CSV generators
# ---------------------------------------------------------------------------

def _income_csv_range(start: date, end: date) -> str:
    from dailyLedger.models import Income

    buf    = io.StringIO()
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
        .filter(date__range=(start, end))
        .select_related('session', 'fees_account')
        .order_by('date', 'id')
    )
    for e in qs:
        writer.writerow([
            e.date, e.voucher_number,
            e.session.session if e.session else '',
            e.major_head, e.head, e.sub_head,
            e.amount, e.payment_type,
            e.fees_account.account_id if e.fees_account else '',
            e.fees_account.name       if e.fees_account else '',
            e.details,
        ])
    return buf.getvalue()


def _expense_csv_range(start: date, end: date) -> str:
    from dailyLedger.models import Expense

    buf    = io.StringIO()
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
        .filter(date__range=(start, end))
        .select_related('session', 'employee')
        .order_by('date', 'id')
    )
    for e in qs:
        writer.writerow([
            e.date, e.voucher_number,
            e.session.session if e.session else '',
            e.major_head, e.head, e.sub_head,
            e.amount, e.payment_type,
            e.employee.emp_no if e.employee else '',
            e.employee.name   if e.employee else '',
            e.details,
        ])
    return buf.getvalue()


def _payroll_csv_months(month_list: list) -> str:
    from employees.models import EmployeePayrollEntry

    buf    = io.StringIO()
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
        .filter(month__in=month_list)
        .select_related('employee', 'session')
        .order_by('month', 'employee__name')
    )
    for e in qs:
        total = (e.payable_salary or 0) + e.old_dues + e.other_amount
        writer.writerow([
            e.employee.emp_no, e.employee.name, e.employee.post,
            e.session.session if e.session else '',
            e.month,
            e.employee.base_salary_per_month,
            e.payable_salary if e.payable_salary is not None else '',
            e.old_dues, e.other_amount, total,
            e.note,
        ])
    return buf.getvalue()


def _fees_summary_csv_range(start: date, end: date) -> str:
    from dailyLedger.models import Income

    buf    = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'Fees Account ID', 'Fees Account Name',
        'No. of Payments', 'Total Collected (Rs)',
    ])

    qs = (
        Income.objects
        .filter(date__range=(start, end), fees_account__isnull=False)
        .values('fees_account__account_id', 'fees_account__name')
        .annotate(payment_count=Count('id'), total=Sum('amount'))
        .order_by('fees_account__account_id')
    )
    for row in qs:
        writer.writerow([
            row['fees_account__account_id'],
            row['fees_account__name'],
            row['payment_count'],
            row['total'],
        ])

    totals = Income.objects.filter(
        date__range=(start, end), fees_account__isnull=False
    ).aggregate(total=Sum('amount'), count=Count('id'))
    writer.writerow([])
    writer.writerow(['TOTAL', '', totals['count'] or 0, totals['total'] or 0])

    return buf.getvalue()

