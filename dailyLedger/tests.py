from datetime import date
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
import csv

from .models import Expense, Income, Head, Session


def make_session(label='2025-2026', status='current_session'):
    return Session.objects.create(session=label, status=status)


def make_head(major='Salary', head='Teaching', sub='', ledger_type='Expense'):
    return Head.objects.create(major_head=major, head=head, sub_head=sub, ledger_type=ledger_type)


# ── Model: Session ────────────────────────────────────────────────────────────

class SessionModelTests(TestCase):
    def test_str(self):
        s = make_session('2025-2026')
        self.assertEqual(str(s), '2025-2026')

    def test_unique_session_label(self):
        make_session('2025-2026')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            make_session('2025-2026')


# ── Model: Head ───────────────────────────────────────────────────────────────

class HeadModelTests(TestCase):
    def test_str(self):
        h = make_head('Salary', 'Teaching', 'Primary')
        self.assertEqual(str(h), 'Salary / Teaching / Primary')

    def test_unique_together(self):
        make_head('Salary', 'Teaching', 'Primary')
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            make_head('Salary', 'Teaching', 'Primary')

    def test_default_status_active(self):
        h = make_head()
        self.assertEqual(h.status, 'Active')


# ── Model: Expense ────────────────────────────────────────────────────────────

class ExpenseModelTests(TestCase):
    def setUp(self):
        self.session = make_session()

    def test_voucher_auto_generated(self):
        exp = Expense.objects.create(date=date(2026, 1, 1), amount=500, session=self.session)
        self.assertTrue(exp.voucher_number.startswith('EXP-'))

    def test_voucher_increments(self):
        e1 = Expense.objects.create(date=date(2026, 1, 1), amount=100, session=self.session)
        e2 = Expense.objects.create(date=date(2026, 1, 2), amount=200, session=self.session)
        n1 = int(e1.voucher_number.split('-')[-1])
        n2 = int(e2.voucher_number.split('-')[-1])
        self.assertEqual(n2, n1 + 1)

    def test_manual_voucher_respected(self):
        exp = Expense.objects.create(
            date=date(2026, 1, 1), amount=500,
            voucher_number='CUSTOM-001', session=self.session
        )
        self.assertEqual(exp.voucher_number, 'CUSTOM-001')

    def test_str(self):
        exp = Expense.objects.create(date=date(2026, 1, 1), amount=1000, session=self.session)
        self.assertIn(str(exp.amount), str(exp))

    def test_amount_stored_correctly(self):
        exp = Expense.objects.create(date=date(2026, 1, 1), amount=Decimal('1234.56'), session=self.session)
        exp.refresh_from_db()
        self.assertEqual(exp.amount, Decimal('1234.56'))

    def test_employee_link_optional(self):
        exp = Expense.objects.create(date=date(2026, 1, 1), amount=500, session=self.session)
        self.assertIsNone(exp.employee)


# ── Model: Income ─────────────────────────────────────────────────────────────

class IncomeModelTests(TestCase):
    def setUp(self):
        self.session = make_session()

    def test_voucher_auto_generated(self):
        inc = Income.objects.create(date=date(2026, 1, 1), amount=1000, session=self.session)
        self.assertTrue(inc.voucher_number.startswith('V'))

    def test_voucher_increments(self):
        i1 = Income.objects.create(date=date(2026, 1, 1), amount=100, session=self.session)
        i2 = Income.objects.create(date=date(2026, 1, 2), amount=200, session=self.session)
        n1 = int(i1.voucher_number[1:])
        n2 = int(i2.voucher_number[1:])
        self.assertEqual(n2, n1 + 1)

    def test_str(self):
        inc = Income.objects.create(date=date(2026, 1, 1), amount=500, session=self.session)
        self.assertIn('Income', str(inc))

    def test_amount_stored_correctly(self):
        inc = Income.objects.create(date=date(2026, 1, 1), amount=Decimal('9999.99'), session=self.session)
        inc.refresh_from_db()
        self.assertEqual(inc.amount, Decimal('9999.99'))


# ── Ledger filtering / aggregation logic ─────────────────────────────────────

class LedgerFilterTests(TestCase):
    def setUp(self):
        self.s1 = make_session('2025-2026')
        self.s2 = Session.objects.create(session='2024-2025', status='old_session')
        Expense.objects.create(date=date(2026, 1, 1), amount=1000, session=self.s1, major_head='Salary')
        Expense.objects.create(date=date(2026, 2, 1), amount=2000, session=self.s1, major_head='Maintenance')
        Expense.objects.create(date=date(2025, 1, 1), amount=500,  session=self.s2, major_head='Salary')
        Income.objects.create(date=date(2026, 1, 5), amount=5000, session=self.s1, major_head='Fees')
        Income.objects.create(date=date(2026, 2, 5), amount=3000, session=self.s1, major_head='Fees')

    def test_expense_filter_by_session(self):
        qs = Expense.objects.filter(session=self.s1)
        self.assertEqual(qs.count(), 2)

    def test_expense_filter_by_major_head(self):
        qs = Expense.objects.filter(session=self.s1, major_head='Salary')
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().amount, Decimal('1000'))

    def test_income_total_for_session(self):
        from django.db.models import Sum
        total = Income.objects.filter(session=self.s1).aggregate(t=Sum('amount'))['t']
        self.assertEqual(total, Decimal('8000'))

    def test_expense_session_isolation(self):
        """Expenses from another session must not bleed into s1."""
        qs = Expense.objects.filter(session=self.s1, major_head='Salary')
        self.assertEqual(qs.count(), 1)  # s2's salary expense must be excluded


# ── View tests ────────────────────────────────────────────────────────────────

class LedgerViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_superuser('admin', 'a@a.com', 'pass')
        self.client.login(username='admin', password='pass')
        self.session = make_session()

    def test_expenses_home_loads(self):
        resp = self.client.get(reverse('expenses_home'))
        self.assertEqual(resp.status_code, 200)

    def test_income_home_loads(self):
        resp = self.client.get(reverse('income_home'))
        self.assertEqual(resp.status_code, 200)

    def test_heads_home_loads(self):
        resp = self.client.get(reverse('heads_home'))
        self.assertEqual(resp.status_code, 200)

    def test_session_ledger_report_loads(self):
        resp = self.client.get(reverse('session_ledger_report'))
        self.assertEqual(resp.status_code, 200)

    def test_session_ledger_report_with_session(self):
        Expense.objects.create(date=date(2026, 1, 1), amount=1000, session=self.session, major_head='Salary')
        Income.objects.create(date=date(2026, 1, 5), amount=5000, session=self.session, major_head='Fees')
        resp = self.client.get(reverse('session_ledger_report'), {'session': self.session.id})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Salary')
        self.assertContains(resp, 'Fees')

    def test_monthly_ledger_report_loads(self):
        resp = self.client.get(reverse('monthly_ledger_report'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Monthly Ledger Report')

    def test_monthly_ledger_report_with_filters(self):
        Income.objects.create(date=date(2025, 4, 10), amount=6000, session=self.session, major_head='Fees')
        Expense.objects.create(date=date(2025, 4, 18), amount=2000, session=self.session, major_head='Salary')
        resp = self.client.get(reverse('monthly_ledger_report'), {
            'session': self.session.id,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'April')
        self.assertContains(resp, 'Fees')
        self.assertContains(resp, 'Salary')

    def test_monthly_ledger_report_csv_export(self):
        Income.objects.create(date=date(2025, 4, 10), amount=6000, session=self.session, major_head='Fees')
        resp = self.client.get(reverse('monthly_ledger_report_csv'), {
            'session': self.session.id,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'text/csv')
        csv_text = resp.content.decode('utf-8')
        reader = list(csv.reader(csv_text.splitlines()))
        self.assertTrue(reader[0][0] == 'Month')

    def test_monthly_ledger_report_pdf_view(self):
        resp = self.client.get(reverse('monthly_ledger_report_pdf'), {
            'session': self.session.id,
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Monthly Ledger Report')

    def test_add_expense_via_post(self):
        make_head('Salary', 'Teaching', '', 'Expense')
        resp = self.client.post(reverse('expenses_home'), {
            'date': '2026-01-15',
            'amount': '1500',
            'major_head': 'Salary',
            'head': 'Teaching',
            'sub_head': '',
            'details': 'January salary',
            'payment_type': 'Cash',
            'session': self.session.id,
        })
        self.assertIn(resp.status_code, [200, 302])
        self.assertTrue(Expense.objects.filter(amount=1500).exists())

    def test_delete_expense(self):
        exp = Expense.objects.create(date=date(2026, 1, 1), amount=500, session=self.session)
        resp = self.client.post(reverse('delete_expense', args=[exp.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Expense.objects.filter(pk=exp.pk).exists())

    def test_delete_income(self):
        inc = Income.objects.create(date=date(2026, 1, 1), amount=500, session=self.session)
        resp = self.client.post(reverse('delete_income', args=[inc.pk]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Income.objects.filter(pk=inc.pk).exists())

    def test_expense_filter_by_session_in_view(self):
        s2 = Session.objects.create(session='2024-2025', status='old_session')
        Expense.objects.create(date=date(2026, 1, 1), amount=1000, session=self.session, major_head='Salary')
        Expense.objects.create(date=date(2025, 1, 1), amount=999,  session=s2, major_head='Other')
        resp = self.client.get(reverse('expenses_home'), {'session': self.session.id})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '1000')
        self.assertNotContains(resp, '999')
