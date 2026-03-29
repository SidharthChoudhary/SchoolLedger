from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from decimal import Decimal

from .models import Employee, EmployeePayrollEntry
from dailyLedger.models import Session, Expense


def make_session(label='2025-2026'):
    return Session.objects.create(session=label)


def make_employee(name='Test Employee', salary=8000):
    return Employee.objects.create(name=name, base_salary_per_month=salary, status='active')


def make_entry(session, emp, month, payable=0, old_dues=0, other_amount=0):
    return EmployeePayrollEntry.objects.create(
        session=session, employee=emp, month=month,
        payable_salary=payable, old_dues=old_dues, other_amount=other_amount,
    )


# ── Model tests ───────────────────────────────────────────────────────────────

class EmployeeModelTests(TestCase):
    def test_emp_no_auto_assigned(self):
        emp = make_employee()
        self.assertIsNotNone(emp.emp_no)
        self.assertGreaterEqual(emp.emp_no, 1000)

    def test_emp_no_increments(self):
        e1 = make_employee('Alice')
        e2 = make_employee('Bob')
        self.assertEqual(e2.emp_no, e1.emp_no + 1)

    def test_str(self):
        emp = make_employee('Jane')
        self.assertEqual(str(emp), 'Jane')


class EmployeePayrollEntryTests(TestCase):
    def setUp(self):
        self.session = make_session()
        self.emp = make_employee(salary=8000)

    def test_unique_together(self):
        make_entry(self.session, self.emp, '2026-01', payable=4000)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            make_entry(self.session, self.emp, '2026-01', payable=5000)

    def test_str(self):
        entry = make_entry(self.session, self.emp, '2026-01', payable=4000)
        self.assertIn('2026-01', str(entry))
        self.assertIn(self.emp.name, str(entry))


# ── Payroll salary formula tests ─────────────────────────────────────────────

class PayrollSalaryFormulaTests(TestCase):
    """Test the salary formula: base / 30 × work_days, capped at monthly salary."""

    def _calc(self, monthly_salary, work_days, leave, days_in_month):
        """Mirror the view formula."""
        total_tracked = work_days + leave
        if leave <= 2 and total_tracked >= days_in_month - 2:
            return monthly_salary
        return min(round((monthly_salary / 30) * work_days, 2), monthly_salary)

    def test_15_days_half_salary(self):
        result = self._calc(8000, 15, 16, 31)
        self.assertEqual(result, 4000.0)

    def test_full_month_returns_full_salary(self):
        result = self._calc(8000, 31, 0, 31)
        self.assertEqual(result, 8000)

    def test_full_month_with_2_leaves(self):
        result = self._calc(8000, 29, 2, 31)
        self.assertEqual(result, 8000)

    def test_capped_at_monthly_salary(self):
        # 31 work days on a 30-day divisor would exceed salary — must be capped
        result = self._calc(8000, 31, 0, 30)
        self.assertLessEqual(result, 8000)

    def test_zero_work_days(self):
        result = self._calc(8000, 0, 31, 31)
        self.assertEqual(result, 0)

    def test_5000_salary_15_days(self):
        result = self._calc(5000, 15, 16, 31)
        self.assertEqual(result, 2500.0)


# ── View tests ────────────────────────────────────────────────────────────────

class PayrollViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.client.login(username='admin', password='pass')
        self.session = make_session()
        self.emp = make_employee('Anita Choudhary', salary=8000)

    def test_payroll_page_loads(self):
        url = reverse('employee_payroll_unified')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_payroll_page_with_session_and_month(self):
        url = reverse('employee_payroll_unified')
        make_entry(self.session, self.emp, '2026-01', payable=4000, old_dues=500, other_amount=20)
        resp = self.client.get(url, {'session': self.session.id, 'month': '2026-01'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Anita Choudhary')

    def test_salary_statement_page_loads(self):
        url = reverse('employee_full_salary_statement')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_salary_statement_with_employee(self):
        make_entry(self.session, self.emp, '2026-01', payable=4000, old_dues=500, other_amount=20)
        url = reverse('employee_full_salary_statement')
        resp = self.client.get(url, {'session': self.session.id, 'employee': self.emp.id})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Anita Choudhary')

    def test_salary_statement_amount_includes_old_dues_and_other(self):
        """Payable Amount = salary + old_dues + other_amount"""
        make_entry(self.session, self.emp, '2026-01', payable=4000, old_dues=500, other_amount=20)
        url = reverse('employee_full_salary_statement')
        resp = self.client.get(url, {'session': self.session.id, 'employee': self.emp.id})
        # 4000 + 500 + 20 = 4520
        self.assertContains(resp, '4520')

    def test_salary_summary_page_loads(self):
        url = reverse('employees_salary_statement')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_salary_summary_other_amount_separate(self):
        """Summary page shows other_amount as its own column."""
        make_entry(self.session, self.emp, '2026-01', payable=4000, old_dues=0, other_amount=150)
        url = reverse('employees_salary_statement')
        resp = self.client.get(url, {'session': self.session.id})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Other Amount')


# ── Payroll generate POST tests ───────────────────────────────────────────────

class PayrollGenerateTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.client.login(username='admin', password='pass')
        self.session = make_session()
        self.emp = make_employee('Test Staff', salary=6000)

    def test_generate_creates_payroll_entry(self):
        url = reverse('employee_payroll_unified')
        resp = self.client.post(url, {
            'action': 'generate',
            'session': self.session.id,
            'month': '2026-02',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(EmployeePayrollEntry.objects.filter(
            session=self.session, employee=self.emp, month='2026-02'
        ).exists())

    def test_save_updates_payable_salary(self):
        entry = make_entry(self.session, self.emp, '2026-02', payable=3000)
        url = reverse('employee_payroll_unified')
        self.client.post(url, {
            'action': 'save',
            'session': self.session.id,
            'month': '2026-02',
            f'payable_{self.emp.id}': '5500',
            f'old_dues_{self.emp.id}': '0',
            f'other_{self.emp.id}': '0',
        })
        entry.refresh_from_db()
        self.assertEqual(float(entry.payable_salary), 5500.0)


# ── Bulk Import Payroll tests ─────────────────────────────────────────────────

import io

def make_csv(*rows, header=True):
    """Build an in-memory CSV upload file from a list of dicts (or raw rows)."""
    lines = []
    if header:
        lines.append('Emp_ID,Month,Payable_Salary,Old_Dues,Other_Amount,Note,Manual_Work_Days,Manual_Leave_Days')
    for row in rows:
        lines.append(row)
    content = '\n'.join(lines) + '\n'
    return io.BytesIO(content.encode('utf-8'))


class BulkImportPayrollTemplateDownloadTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.client.login(username='admin', password='pass')

    def test_template_download_returns_csv(self):
        resp = self.client.get(reverse('download_payroll_template'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        self.assertIn('attachment', resp['Content-Disposition'])
        self.assertIn('.csv', resp['Content-Disposition'])

    def test_template_contains_required_headers(self):
        resp = self.client.get(reverse('download_payroll_template'))
        content = resp.content.decode('utf-8')
        for col in ('Emp_ID', 'Month', 'Payable_Salary', 'Old_Dues', 'Other_Amount'):
            self.assertIn(col, content)


class BulkImportPayrollPageTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.client.login(username='admin', password='pass')

    def test_page_loads(self):
        resp = self.client.get(reverse('bulk_import_payroll'))
        self.assertEqual(resp.status_code, 200)

    def test_page_contains_form(self):
        resp = self.client.get(reverse('bulk_import_payroll'))
        self.assertContains(resp, 'csv_file')
        self.assertContains(resp, 'handle_duplicates')
        self.assertContains(resp, 'dry_run')

    def test_page_contains_download_link(self):
        resp = self.client.get(reverse('bulk_import_payroll'))
        self.assertContains(resp, reverse('download_payroll_template'))


class BulkImportPayrollImportTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.client.login(username='admin', password='pass')
        self.session = make_session('2025-2026')
        self.emp = make_employee('Anita Sharma', salary=8000)

    def _post(self, csv_content, handle_duplicates='skip', dry_run=False):
        f = io.BytesIO(csv_content.encode('utf-8'))
        f.name = 'payroll.csv'
        data = {
            'csv_file': f,
            'handle_duplicates': handle_duplicates,
        }
        if dry_run:
            data['dry_run'] = 'on'
        return self.client.post(reverse('bulk_import_payroll'), data, format='multipart')

    # ── Happy-path imports ──────────────────────────────────────────────────

    def test_creates_entry_for_valid_row(self):
        csv = (
            'Emp_ID,Month,Payable_Salary,Old_Dues,Other_Amount,Note,Manual_Work_Days,Manual_Leave_Days\n'
            f'{self.emp.emp_no},2025-06,8000,0,0,,,'
        )
        self._post(csv)
        self.assertTrue(EmployeePayrollEntry.objects.filter(
            session=self.session, employee=self.emp, month='2025-06'
        ).exists())

    def test_payable_salary_stored_correctly(self):
        csv = (
            'Emp_ID,Month,Payable_Salary,Old_Dues,Other_Amount,Note,Manual_Work_Days,Manual_Leave_Days\n'
            f'{self.emp.emp_no},2025-07,6500,500,200,Bonus,,'
        )
        self._post(csv)
        entry = EmployeePayrollEntry.objects.get(
            session=self.session, employee=self.emp, month='2025-07'
        )
        self.assertEqual(float(entry.payable_salary), 6500.0)
        self.assertEqual(float(entry.old_dues), 500.0)
        self.assertEqual(float(entry.other_amount), 200.0)
        self.assertEqual(entry.note, 'Bonus')

    def test_january_maps_to_correct_session(self):
        """Jan 2026 belongs to session 2025-2026."""
        csv = (
            'Emp_ID,Month,Payable_Salary\n'
            f'{self.emp.emp_no},2026-01,7000'
        )
        self._post(csv)
        self.assertTrue(EmployeePayrollEntry.objects.filter(
            session=self.session, employee=self.emp, month='2026-01'
        ).exists())

    def test_march_maps_to_correct_session(self):
        """March 2026 belongs to session 2025-2026."""
        csv = (
            'Emp_ID,Month,Payable_Salary\n'
            f'{self.emp.emp_no},2026-03,7000'
        )
        self._post(csv)
        self.assertTrue(EmployeePayrollEntry.objects.filter(
            session=self.session, employee=self.emp, month='2026-03'
        ).exists())

    def test_april_maps_to_correct_session(self):
        """April 2025 belongs to session 2025-2026."""
        csv = (
            'Emp_ID,Month,Payable_Salary\n'
            f'{self.emp.emp_no},2025-04,8000'
        )
        self._post(csv)
        self.assertTrue(EmployeePayrollEntry.objects.filter(
            session=self.session, employee=self.emp, month='2025-04'
        ).exists())

    def test_multiple_rows_created(self):
        csv = (
            'Emp_ID,Month,Payable_Salary\n'
            f'{self.emp.emp_no},2025-04,8000\n'
            f'{self.emp.emp_no},2025-05,8000\n'
            f'{self.emp.emp_no},2025-06,8000\n'
        )
        self._post(csv)
        count = EmployeePayrollEntry.objects.filter(session=self.session, employee=self.emp).count()
        self.assertEqual(count, 3)

    def test_manual_work_days_stored(self):
        csv = (
            'Emp_ID,Month,Payable_Salary,Old_Dues,Other_Amount,Note,Manual_Work_Days,Manual_Leave_Days\n'
            f'{self.emp.emp_no},2025-08,5000,0,0,,20,2'
        )
        self._post(csv)
        entry = EmployeePayrollEntry.objects.get(
            session=self.session, employee=self.emp, month='2025-08'
        )
        self.assertEqual(float(entry.manual_work_days), 20.0)
        self.assertEqual(entry.manual_leave_days, 2)

    def test_optional_columns_default_to_zero(self):
        """A minimal CSV (only required columns) should default Old_Dues and Other_Amount to 0."""
        csv = (
            'Emp_ID,Month,Payable_Salary\n'
            f'{self.emp.emp_no},2025-09,4000'
        )
        self._post(csv)
        entry = EmployeePayrollEntry.objects.get(
            session=self.session, employee=self.emp, month='2025-09'
        )
        self.assertEqual(float(entry.old_dues), 0.0)
        self.assertEqual(float(entry.other_amount), 0.0)

    # ── Dry-run mode ────────────────────────────────────────────────────────

    def test_dry_run_does_not_create_entry(self):
        csv = (
            'Emp_ID,Month,Payable_Salary\n'
            f'{self.emp.emp_no},2025-10,8000'
        )
        self._post(csv, dry_run=True)
        self.assertFalse(EmployeePayrollEntry.objects.filter(
            session=self.session, employee=self.emp, month='2025-10'
        ).exists())

    def test_dry_run_response_contains_preview(self):
        csv = (
            'Emp_ID,Month,Payable_Salary\n'
            f'{self.emp.emp_no},2025-11,8000'
        )
        resp = self._post(csv, dry_run=True)
        self.assertContains(resp, 'Dry-Run Preview')

    # ── Duplicate handling ──────────────────────────────────────────────────

    def test_duplicate_skipped(self):
        make_entry(self.session, self.emp, '2025-12', payable=5000)
        csv = (
            'Emp_ID,Month,Payable_Salary\n'
            f'{self.emp.emp_no},2025-12,9000'
        )
        self._post(csv, handle_duplicates='skip')
        entry = EmployeePayrollEntry.objects.get(
            session=self.session, employee=self.emp, month='2025-12'
        )
        # Original value preserved
        self.assertEqual(float(entry.payable_salary), 5000.0)

    def test_duplicate_update(self):
        make_entry(self.session, self.emp, '2025-12', payable=5000)
        csv = (
            'Emp_ID,Month,Payable_Salary\n'
            f'{self.emp.emp_no},2025-12,9999'
        )
        self._post(csv, handle_duplicates='update')
        entry = EmployeePayrollEntry.objects.get(
            session=self.session, employee=self.emp, month='2025-12'
        )
        self.assertEqual(float(entry.payable_salary), 9999.0)

    # ── Validation errors ───────────────────────────────────────────────────

    def test_unknown_emp_id_rejected(self):
        csv = (
            'Emp_ID,Month,Payable_Salary\n'
            '9999,2025-06,8000'
        )
        self._post(csv)
        # No entry created
        self.assertEqual(EmployeePayrollEntry.objects.count(), 0)

    def test_invalid_month_format_rejected(self):
        csv = (
            'Emp_ID,Month,Payable_Salary\n'
            f'{self.emp.emp_no},June-2025,8000'
        )
        self._post(csv)
        self.assertEqual(EmployeePayrollEntry.objects.count(), 0)

    def test_non_numeric_salary_rejected(self):
        csv = (
            'Emp_ID,Month,Payable_Salary\n'
            f'{self.emp.emp_no},2025-06,EIGHT_THOUSAND'
        )
        self._post(csv)
        self.assertEqual(EmployeePayrollEntry.objects.count(), 0)

    def test_missing_required_column_shows_error(self):
        """CSV missing Payable_Salary should show an error."""
        csv = 'Emp_ID,Month\n1000,2025-06'
        resp = self._post(csv)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Payable_Salary')

    def test_session_not_in_db_rejected(self):
        """Month whose auto-detected session does not exist in DB should be rejected."""
        csv = (
            'Emp_ID,Month,Payable_Salary\n'
            f'{self.emp.emp_no},2010-04,8000'   # session 2010-2011 doesn't exist
        )
        self._post(csv)
        self.assertEqual(EmployeePayrollEntry.objects.count(), 0)

    def test_empty_file_shows_error(self):
        resp = self._post('', dry_run=False)
        self.assertEqual(resp.status_code, 200)

    # ── Session auto-detection helper ───────────────────────────────────────

    def test_session_detection_boundary_months(self):
        from employees.views import _month_to_session_str
        self.assertEqual(_month_to_session_str('2025-04'), '2025-2026')
        self.assertEqual(_month_to_session_str('2025-12'), '2025-2026')
        self.assertEqual(_month_to_session_str('2026-01'), '2025-2026')
        self.assertEqual(_month_to_session_str('2026-03'), '2025-2026')
        self.assertEqual(_month_to_session_str('2026-04'), '2026-2027')

