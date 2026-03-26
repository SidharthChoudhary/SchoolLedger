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
