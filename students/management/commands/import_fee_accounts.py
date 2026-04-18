"""
Management command — Import fee accounts, link students, and import agreed fees.

Steps (run in order, or individually):
  Step 1 — Create FeesAccount records from fees_accounts.csv
  Step 2 — Link students to accounts from students_accounts_link.csv
  Step 3 — Create FeesAccountAgreement records from fees_agreements.csv

CSV files expected in:
  datamigration/convertedcsvs/fees_accounts.csv
  datamigration/convertedcsvs/students_accounts_link.csv
  datamigration/convertedcsvs/fees_agreements.csv

Usage:
    python manage.py import_fee_accounts                        # all 3 steps
    python manage.py import_fee_accounts --step 1              # accounts only
    python manage.py import_fee_accounts --step 2              # link only
    python manage.py import_fee_accounts --step 3              # agreements only
    python manage.py import_fee_accounts --dry-run             # preview, no DB writes

CSV formats:
  fees_accounts.csv:
    account_id, name, account_open, account_status, register_page
    001, Smith John-SRN101, 2024-04-01, open, 12

  students_accounts_link.csv:
    srn, account_id
    SRN101, 001

  fees_agreements.csv:
    account_id, session, tuition_fees, tc_fees, admission_fees,
    book_set, book_diary, book_other,
    uniform_shirt, uniform_pant, uniform_sweater, uniform_hoody,
    uniform_t_shirt, uniform_tie, uniform_belt, uniform_id_card, bus_fees
    001, 2024-25, 12000, 500, 0, 800, 200, 0, 600, 400, 800, 0, 0, 100, 0, 50, 1200
"""

import csv
import os
from datetime import date

from django.core.management.base import BaseCommand, CommandError

CSV_DIR = 'datamigration/convertedcsvs'

ACCOUNTS_CSV    = os.path.join(CSV_DIR, 'fees_accounts.csv')
LINK_CSV        = os.path.join(CSV_DIR, 'students_accounts_link.csv')
AGREEMENTS_CSV  = os.path.join(CSV_DIR, 'fees_agreements.csv')

AGREEMENT_FEE_FIELDS = [
    'tuition_fees', 'tc_fees', 'admission_fees',
    'book_set', 'book_diary', 'book_other',
    'uniform_shirt', 'uniform_pant', 'uniform_sweater', 'uniform_hoody',
    'uniform_t_shirt', 'uniform_tie', 'uniform_belt', 'uniform_id_card',
    'bus_fees',
]


class Command(BaseCommand):
    help = 'Import fee accounts, link students, and import agreed fees from CSVs.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Parse and report without writing to DB'
        )
        parser.add_argument(
            '--step', type=int, choices=[1, 2, 3], default=0,
            help='Run only a specific step (1=accounts, 2=link, 3=agreements). Default: all.'
        )
        parser.add_argument('--accounts-csv',   default=ACCOUNTS_CSV)
        parser.add_argument('--link-csv',        default=LINK_CSV)
        parser.add_argument('--agreements-csv',  default=AGREEMENTS_CSV)

    def handle(self, *args, **options):
        dry_run   = options['dry_run']
        step      = options['step']
        acct_path = options['accounts_csv']
        link_path = options['link_csv']
        agr_path  = options['agreements_csv']

        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] No changes will be written to the database.\n'))

        run_all = step == 0

        if run_all or step == 1:
            self._check_file(acct_path)
            self._import_accounts(acct_path, dry_run)

        if run_all or step == 2:
            self._check_file(link_path)
            self._link_students(link_path, dry_run)

        if run_all or step == 3:
            self._check_file(agr_path)
            self._import_agreements(agr_path, dry_run)

        if dry_run:
            self.stdout.write(self.style.WARNING('\n[DRY RUN] Nothing was written to the database.'))
        else:
            self.stdout.write(self.style.SUCCESS('\n[DONE] Import completed successfully.'))

    # ── helpers ──────────────────────────────────────────────────────────────

    def _check_file(self, path):
        if not os.path.exists(path):
            raise CommandError(f'CSV file not found: {path}')

    def _read_csv(self, path):
        with open(path, encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            return [
                {k.strip(): v.strip() for k, v in row.items()}
                for row in reader
            ]

    # ── Step 1: Create FeesAccounts ─────────────────────────────────────────

    def _import_accounts(self, path, dry_run):
        from students.models import FeesAccount

        self.stdout.write(f'\n-- Step 1: Creating FeesAccounts from {os.path.basename(path)} --')
        rows = self._read_csv(path)

        created = skipped = errors = 0

        for i, row in enumerate(rows, start=2):  # row 1 is header
            account_id = row.get('account_id', '').strip()
            name       = row.get('name', '').strip()
            acct_open  = row.get('account_open', '').strip()
            status     = row.get('account_status', 'open').strip() or 'open'
            reg_page   = row.get('register_page', '').strip() or None

            if not account_id or not name:
                self.stdout.write(self.style.ERROR(
                    f'  Row {i}: skipped — account_id and name are required. Got: {row}'
                ))
                errors += 1
                continue

            if not acct_open:
                acct_open_date = date.today()
            else:
                try:
                    from datetime import datetime
                    acct_open_date = datetime.strptime(acct_open, '%Y-%m-%d').date()
                except ValueError:
                    self.stdout.write(self.style.ERROR(
                        f'  Row {i}: invalid account_open date "{acct_open}" — expected YYYY-MM-DD. Skipping.'
                    ))
                    errors += 1
                    continue

            if FeesAccount.objects.filter(account_id=account_id).exists():
                self.stdout.write(f'  Row {i}: account_id "{account_id}" already exists — skipped.')
                skipped += 1
                continue

            self.stdout.write(f'  Row {i}: CREATE account "{account_id}" — {name}')
            if not dry_run:
                # Bypass auto-generate in save() by using update_or_create with explicit account_id
                FeesAccount.objects.create(
                    account_id=account_id,
                    name=name,
                    account_open=acct_open_date,
                    account_status=status,
                    register_page=reg_page,
                )
            created += 1

        self.stdout.write(
            self.style.SUCCESS(f'  Step 1 done — created: {created}, skipped: {skipped}, errors: {errors}')
        )

    # ── Step 2: Link Students to Accounts ───────────────────────────────────

    def _link_students(self, path, dry_run):
        from students.models import Student, FeesAccount

        self.stdout.write(f'\n-- Step 2: Linking students from {os.path.basename(path)} --')
        rows = self._read_csv(path)

        linked = skipped = errors = 0

        for i, row in enumerate(rows, start=2):
            srn        = row.get('srn', '').strip()
            account_id = row.get('account_id', '').strip()

            if not srn or not account_id:
                self.stdout.write(self.style.ERROR(
                    f'  Row {i}: skipped — srn and account_id are required. Got: {row}'
                ))
                errors += 1
                continue

            try:
                student = Student.objects.get(srn=srn)
            except Student.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f'  Row {i}: student with SRN "{srn}" not found — skipped.'
                ))
                errors += 1
                continue

            try:
                account = FeesAccount.objects.get(account_id=account_id)
            except FeesAccount.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f'  Row {i}: FeesAccount "{account_id}" not found — skipped.'
                    f' (Run Step 1 first, or check account_id value)'
                ))
                errors += 1
                continue

            if student.fees_account_id == account.pk:
                self.stdout.write(f'  Row {i}: SRN "{srn}" already linked to "{account_id}" — skipped.')
                skipped += 1
                continue

            self.stdout.write(
                f'  Row {i}: LINK SRN "{srn}" ({student.first_name} {student.last_name}) → account "{account_id}"'
            )
            if not dry_run:
                student.fees_account = account
                student.save(update_fields=['fees_account'])
            linked += 1

        self.stdout.write(
            self.style.SUCCESS(f'  Step 2 done — linked: {linked}, skipped: {skipped}, errors: {errors}')
        )

    # ── Step 3: Import FeesAccountAgreements ────────────────────────────────

    def _import_agreements(self, path, dry_run):
        from students.models import FeesAccount, FeesAccountAgreement
        from dailyLedger.models import Session

        self.stdout.write(f'\n-- Step 3: Importing agreements from {os.path.basename(path)} --')
        rows = self._read_csv(path)

        created = updated = errors = 0

        for i, row in enumerate(rows, start=2):
            account_id   = row.get('account_id', '').strip()
            session_str  = row.get('session', '').strip()

            if not account_id or not session_str:
                self.stdout.write(self.style.ERROR(
                    f'  Row {i}: skipped — account_id and session are required. Got: {row}'
                ))
                errors += 1
                continue

            try:
                account = FeesAccount.objects.get(account_id=account_id)
            except FeesAccount.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f'  Row {i}: FeesAccount "{account_id}" not found — skipped.'
                ))
                errors += 1
                continue

            try:
                session = Session.objects.get(session=session_str)
            except Session.DoesNotExist:
                self.stdout.write(self.style.ERROR(
                    f'  Row {i}: Session "{session_str}" not found — skipped.'
                    f' (Check session value matches existing sessions in DB)'
                ))
                errors += 1
                continue

            fee_values = {}
            parse_error = False
            for field in AGREEMENT_FEE_FIELDS:
                raw = row.get(field, '0').strip() or '0'
                try:
                    fee_values[field] = float(raw)
                except ValueError:
                    self.stdout.write(self.style.ERROR(
                        f'  Row {i}: invalid value for "{field}": "{raw}" — skipped.'
                    ))
                    parse_error = True
                    break

            if parse_error:
                errors += 1
                continue

            exists = FeesAccountAgreement.objects.filter(
                fees_account=account, session=session
            ).exists()

            action_label = 'UPDATE' if exists else 'CREATE'
            total = sum(fee_values.values())
            self.stdout.write(
                f'  Row {i}: {action_label} agreement for account "{account_id}" session "{session_str}" — total: {total:,.2f}'
            )

            if not dry_run:
                obj, was_created = FeesAccountAgreement.objects.get_or_create(
                    fees_account=account,
                    session=session,
                    defaults=fee_values,
                )
                if not was_created:
                    for field, value in fee_values.items():
                        setattr(obj, field, value)
                    obj.save()
                    updated += 1
                else:
                    created += 1
            else:
                if exists:
                    updated += 1
                else:
                    created += 1

        self.stdout.write(
            self.style.SUCCESS(f'  Step 3 done — created: {created}, updated: {updated}, errors: {errors}')
        )
