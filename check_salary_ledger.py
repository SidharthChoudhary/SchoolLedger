"""
Validation script: compares Staff Salary Summary 'Paid Amount' total
vs Ledger Expense 'Major Head = Salary' total for a given session.

Run with:   python check_salary_ledger.py [session_id]
If no session_id is given, the current session is used.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
django.setup()

from dailyLedger.models import Expense, Session


# ── Resolve session ──────────────────────────────────────────────────────────
if len(sys.argv) > 1:
    try:
        session = Session.objects.get(pk=int(sys.argv[1]))
    except (Session.DoesNotExist, ValueError):
        print(f"ERROR: Session with id={sys.argv[1]} not found.")
        sys.exit(1)
else:
    session = Session.objects.filter(status='current_session').first()
    if not session:
        session = Session.objects.order_by('-session').first()

if not session:
    print("ERROR: No session found in the database.")
    sys.exit(1)

print(f"\n{'='*64}")
print(f"  Session : {session.session}  (id={session.id})")
print(f"{'='*64}\n")


# ── 1. Salary Summary 'Paid' — all expenses with employee linked ─────────────
paid_qs = Expense.objects.filter(session=session, employee__isnull=False)
paid_total = sum(float(e.amount) for e in paid_qs)

# ── 2. Ledger 'Major Head = Salary' total ────────────────────────────────────
ledger_salary_qs = Expense.objects.filter(session=session, major_head__iexact='Salary')
ledger_total = sum(float(e.amount) for e in ledger_salary_qs)

print(f"  Salary Summary  — Total Paid (employee linked)  : ₹{paid_total:,.2f}")
print(f"  Ledger Expense  — Total (Major Head = Salary)   : ₹{ledger_total:,.2f}")
print(f"  Difference                                       : ₹{abs(paid_total - ledger_total):,.2f}")
print()


# ── 3. In Paid but NOT in Ledger Salary ──────────────────────────────────────
# Expense has employee FK but major_head != 'Salary'
non_salary_employee_qs = (
    Expense.objects
    .filter(session=session, employee__isnull=False)
    .exclude(major_head__iexact='Salary')
    .select_related('employee')
    .order_by('date')
)
non_salary_total = sum(float(e.amount) for e in non_salary_employee_qs)

print(f"--- [A] Employee-linked expenses with major_head != 'Salary'")
print(f"    (counted in Paid, NOT in ledger salary total)")
print(f"    Count: {non_salary_employee_qs.count()}   Total: ₹{non_salary_total:,.2f}")
if non_salary_employee_qs.exists():
    print(f"    {'Date':<12} {'Employee':<30} {'Major Head':<20} {'Amount':>12}")
    print(f"    {'-'*76}")
    for e in non_salary_employee_qs:
        print(f"    {str(e.date):<12} {e.employee.name:<30} {e.major_head or '(blank)':<20} ₹{float(e.amount):>10,.2f}")
print()


# ── 4. In Ledger Salary but NOT in Paid (no employee linked) ─────────────────
no_emp_salary_qs = (
    Expense.objects
    .filter(session=session, major_head__iexact='Salary', employee__isnull=True)
    .order_by('date')
)
no_emp_total = sum(float(e.amount) for e in no_emp_salary_qs)

print(f"--- [B] Salary major-head expenses with NO employee linked")
print(f"    (counted in ledger, NOT in salary summary paid)")
print(f"    Count: {no_emp_salary_qs.count()}   Total: ₹{no_emp_total:,.2f}")
if no_emp_salary_qs.exists():
    print(f"    {'Date':<12} {'Voucher':<16} {'Sub-Head / Details':<35} {'Amount':>12}")
    print(f"    {'-'*76}")
    for e in no_emp_salary_qs:
        label = e.sub_head or e.details or '(blank)'
        print(f"    {str(e.date):<12} {e.voucher_number:<16} {label:<35} ₹{float(e.amount):>10,.2f}")
print()


# ── 5. Summary ────────────────────────────────────────────────────────────────
print(f"{'='*64}")
print(f"  Expected diff  = [B] - [A]  =  ₹{no_emp_total - non_salary_total:,.2f}")
print(f"  Actual diff    = Ledger - Paid = ₹{ledger_total - paid_total:,.2f}")
match = abs((no_emp_total - non_salary_total) - (ledger_total - paid_total)) < 0.01
print(f"  Explanation accounts for diff: {'YES ✓' if match else 'NO — check for other discrepancies'}")
print(f"{'='*64}\n")
