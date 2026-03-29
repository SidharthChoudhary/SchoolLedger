"""
Management command — truncate transaction tables and re-import from CSVs.

Truncates:
  • dailyLedger_expense
  • dailyLedger_income
  • employees_employeepayrollentry

Keeps:
  • employees_employee  (employee master data)
  • dailyLedger_head    (account heads)
  • dailyLedger_session (sessions)
  • all Django internal tables

Then imports from:
  • expense_2024_25.csv   → Expense
  • income_2024_25.csv    → Income
  • payroll_2024_25.csv   → EmployeePayrollEntry

Usage:
    python manage.py reset_and_import
    python manage.py reset_and_import --dry-run
    python manage.py reset_and_import --skip-truncate   # import only, no delete
"""

import csv
import os
import re

from django.core.management.base import BaseCommand, CommandError

CSV_DIR = 'datamigration/convertedcsvs'

EXPENSE_CSV = os.path.join(CSV_DIR, 'expense_2024_25.csv')
INCOME_CSV  = os.path.join(CSV_DIR, 'income_2024_25_fixed.csv')
PAYROLL_CSV = os.path.join(CSV_DIR, 'payroll_2024_25.csv')


def _month_to_session_str(month_str):
    year, mon = int(month_str[:4]), int(month_str[5:7])
    if mon >= 4:
        return f'{year}-{year + 1}'
    return f'{year - 1}-{year}'


class Command(BaseCommand):
    help = 'Truncate Expense/Income/Payroll tables then re-import from converted CSVs.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Parse and report without writing to DB')
        parser.add_argument('--skip-truncate', action='store_true',
                            help='Skip the delete step (import-only)')
        parser.add_argument('--expense-csv', default=EXPENSE_CSV)
        parser.add_argument('--income-csv',  default=INCOME_CSV)
        parser.add_argument('--payroll-csv', default=PAYROLL_CSV)

    def handle(self, *args, **options):
        dry_run       = options['dry_run']
        skip_truncate = options['skip_truncate']
        expense_path  = options['expense_csv']
        income_path   = options['income_csv']
        payroll_path  = options['payroll_csv']

        for path in [expense_path, income_path, payroll_path]:
            if not os.path.exists(path):
                raise CommandError(f'CSV not found: {path}')

        # ── 1. Truncate ─────────────────────────────────────────────────────
        if not skip_truncate:
            self._truncate(dry_run)
        else:
            self.stdout.write(self.style.WARNING('--skip-truncate: keeping existing rows.'))

        # ── 2. Import expense ───────────────────────────────────────────────
        self._import_ledger(expense_path, 'Expense', dry_run)

        # ── 3. Import income ────────────────────────────────────────────────
        self._import_ledger(income_path, 'Income', dry_run)

        # ── 4. Import payroll ───────────────────────────────────────────────
        self._import_payroll(payroll_path, dry_run)

        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] Nothing was written to the database.'))
        else:
            self.stdout.write(self.style.SUCCESS('\n[DONE] All data imported successfully.'))

    # ── helpers ──────────────────────────────────────────────────────────────

    def _truncate(self, dry_run):
        from dailyLedger.models import Expense, Income
        from employees.models import EmployeePayrollEntry

        counts = {
            'Expense':             Expense.objects.count(),
            'Income':              Income.objects.count(),
            'EmployeePayrollEntry': EmployeePayrollEntry.objects.count(),
        }
        self.stdout.write('\n-- Truncating tables --')
        for name, n in counts.items():
            self.stdout.write(f'  {name}: {n} rows will be deleted')

        if not dry_run:
            Expense.objects.all().delete()
            Income.objects.all().delete()
            EmployeePayrollEntry.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('  Tables cleared.'))

    def _import_ledger(self, csv_path, ledger_type, dry_run):
        from dailyLedger.utils import parse_csv_ledger_entries, import_ledger_entries

        self.stdout.write(f'\n-- Importing {ledger_type} from {os.path.basename(csv_path)} --')

        with open(csv_path, encoding='utf-8-sig') as f:
            content = f.read()

        result = parse_csv_ledger_entries(content, handle_duplicates='skip', ledger_type=ledger_type)

        if result['errors']:
            self.stdout.write(self.style.ERROR(f'  Parse errors ({len(result["errors"])}):'))
            for row_num, msg in result['errors'][:20]:
                self.stdout.write(self.style.ERROR(f'    Row {row_num}: {msg}'))

        if result['warnings']:
            self.stdout.write(self.style.WARNING(f'  Warnings ({len(result["warnings"])}):'))
            for row_num, msg in result['warnings'][:10]:
                self.stdout.write(self.style.WARNING(f'    Row {row_num}: {msg}'))

        self.stdout.write(f'  Valid rows : {len(result["valid_rows"])}')
        self.stdout.write(f'  Duplicates : {len(result["duplicate_rows"])}')

        if dry_run or result['errors']:
            if result['errors']:
                self.stdout.write(self.style.ERROR('  Import skipped due to errors.'))
            return

        imp = import_ledger_entries(
            result['valid_rows'], result['duplicate_rows'], 'skip', ledger_type
        )
        self.stdout.write(self.style.SUCCESS(
            f'  Created: {imp["created"]}  Updated: {imp.get("updated", 0)}  Skipped: {imp.get("skipped", 0)}'
        ))

    def _import_payroll(self, csv_path, dry_run):
        from employees.models import Employee, EmployeePayrollEntry
        from dailyLedger.models import Session

        self.stdout.write(f'\n-- Importing Payroll from {os.path.basename(csv_path)} --')

        emp_map     = {str(e.emp_no): e for e in Employee.objects.all()}
        session_map = {s.session: s for s in Session.objects.all()}

        with open(csv_path, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        required = {'Emp_ID', 'Month', 'Payable_Salary'}
        headers = {h.strip() for h in (reader.fieldnames or [])}
        missing = required - headers
        if missing:
            raise CommandError(f'Payroll CSV missing columns: {", ".join(sorted(missing))}')

        valid_rows = []
        row_errors = []

        for row_num, row in enumerate(rows, start=2):
            emp_id_raw   = row.get('Emp_ID', '').strip()
            month_raw    = row.get('Month', '').strip()
            payable_raw  = row.get('Payable_Salary', '').strip()
            old_dues_raw = row.get('Old_Dues', '').strip() or '0'
            other_raw    = row.get('Other_Amount', '').strip() or '0'
            note_raw     = row.get('Note', '').strip()
            work_raw     = row.get('Manual_Work_Days', '').strip()
            leave_raw    = row.get('Manual_Leave_Days', '').strip()

            emp = emp_map.get(emp_id_raw)
            if not emp:
                row_errors.append((row_num, f"Emp_ID '{emp_id_raw}' not found"))
                continue

            if not re.match(r'^\d{4}-(0[1-9]|1[0-2])$', month_raw):
                row_errors.append((row_num, f"Invalid Month '{month_raw}'"))
                continue

            session_str = _month_to_session_str(month_raw)
            session = session_map.get(session_str)
            if not session:
                row_errors.append((row_num, f"Session '{session_str}' not in DB"))
                continue

            try:
                payable   = float(payable_raw)
                old_dues  = float(old_dues_raw)
                other_amt = float(other_raw)
                work_days  = float(work_raw)  if work_raw  else None
                leave_days = int(float(leave_raw)) if leave_raw else None
            except ValueError:
                row_errors.append((row_num, 'Non-numeric value in amount/days column'))
                continue

            valid_rows.append({
                'employee': emp,
                'session':  session,
                'month':    month_raw,
                'payable_salary':    payable,
                'old_dues':          old_dues,
                'other_amount':      other_amt,
                'note':              note_raw,
                'manual_work_days':  work_days,
                'manual_leave_days': leave_days,
            })

        if row_errors:
            self.stdout.write(self.style.ERROR(f'  Row errors ({len(row_errors)}):'))
            for row_num, msg in row_errors[:20]:
                self.stdout.write(self.style.ERROR(f'    Row {row_num}: {msg}'))

        self.stdout.write(f'  Valid rows : {len(valid_rows)}')

        if dry_run or row_errors:
            if row_errors:
                self.stdout.write(self.style.ERROR('  Import skipped due to errors.'))
            return

        created = 0
        for data in valid_rows:
            EmployeePayrollEntry.objects.create(**data)
            created += 1

        self.stdout.write(self.style.SUCCESS(f'  Created: {created}'))
