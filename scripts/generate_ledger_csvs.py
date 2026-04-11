"""
Generate import-ready expense and income CSVs from the DPS accounts workbook.

Usage:
    python scripts/generate_ledger_csvs.py \
        --excel "datamigration/input-accountsExcelFiles/DPS 2025-26 Accounts.xlsm"

Output:
    datamigration/convertedcsvs/expense_2025_26.csv
    datamigration/convertedcsvs/income_2025_26.csv

Rules:
- Expense rows come from the VExp sheet.
- Income rows come from VIncF (fee income) and VIncO (other income).
- Session strings are normalized to the Session format stored in Django.
- Salary expense rows use the employee name from the Name column and try to attach Emp_No.
- Fee income rows default blank fee types to Tuition Fee.
- Other income rows are inferred from their remark text: Loan, Bus Booking, or RTE.
"""

from __future__ import annotations

import argparse
import csv
import difflib
import os
import re
import sys
from pathlib import Path

import django

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
django.setup()

try:
    import openpyxl
except ImportError:
    sys.exit('openpyxl is required: pip install openpyxl')

from dailyLedger.models import Session
from employees.models import Employee


OUTPUT_FIELDS = [
    'Voucher_Number',
    'Date',
    'Amount',
    'Major_Head',
    'Head',
    'Sub_Head',
    'Payment_Type',
    'Session',
    'Details',
]

EXPENSE_FIELDS = ['Emp_No'] + OUTPUT_FIELDS


def normalize_text(value: object) -> str:
    if value is None:
        return ''
    text = str(value).strip()
    return re.sub(r'\s+', ' ', text)


def format_date(value: object) -> str:
    if value is None:
        return ''
    if hasattr(value, 'strftime'):
        return value.strftime('%Y-%m-%d')
    text = normalize_text(value)
    return text


def normalize_amount(value: object) -> str:
    if value is None or value == '':
        return ''
    number = float(value)
    if number.is_integer():
        return str(int(number))
    return f'{number:.2f}'


def build_session_lookup() -> dict[str, str]:
    lookup: dict[str, str] = {}
    for session in Session.objects.all():
        stored = session.session.strip()
        key = stored.lower()
        lookup[key] = stored

        match = re.match(r'^(\d{4})-(\d{4}|\d{2})$', stored)
        if match:
            start = int(match.group(1))
            end = match.group(2)
            if len(end) == 4:
                short = f'{start}-{int(end) % 100:02d}'
                lookup[short.lower()] = stored
            else:
                long_form = f'{start}-{2000 + int(end)}'
                lookup[long_form.lower()] = stored
    return lookup


def workbook_session_label(workbook_name: str, session_lookup: dict[str, str]) -> str:
    match = re.search(r'(\d{4})-(\d{2})', workbook_name)
    if not match:
        return ''
    start = int(match.group(1))
    end_two = int(match.group(2))
    short_form = f'{start}-{end_two:02d}'
    long_form = f'{start}-{2000 + end_two}'
    for candidate in (short_form.lower(), long_form.lower()):
        if candidate in session_lookup:
            return session_lookup[candidate]
    return long_form


def build_employee_lookup() -> tuple[dict[str, int], list[str]]:
    employee_map = {employee.name.strip().lower(): employee.emp_no for employee in Employee.objects.all()}
    return employee_map, list(employee_map.keys())


def match_employee_number(name: str, employee_map: dict[str, int], employee_names: list[str]) -> str:
    key = normalize_text(name).lower()
    if not key:
        return ''
    if key in employee_map:
        return str(employee_map[key])
    matches = difflib.get_close_matches(key, employee_names, n=1, cutoff=0.82)
    if matches:
        return str(employee_map[matches[0]])
    return ''


def infer_payment_type(text: str, sub_head: str) -> str:
    haystack = f'{text} {sub_head}'.lower()
    if 'credit' in haystack:
        return 'Credit'
    if any(token in haystack for token in ['phonepay', 'phone pay', 'pp', 'gpay', 'online', 'bank']):
        return 'Bank Transfer'
    return 'Cash'


def normalize_fee_head(fee_type: str) -> tuple[str, str]:
    fee_type_lower = fee_type.lower()
    if 'bus' in fee_type_lower:
        return 'Fees', 'Bus Fee'
    if 'tc' in fee_type_lower or 'exam' in fee_type_lower:
        return 'Fees', 'TC Fee'
    return 'Fees', 'Tuition Fee'


def classify_other_income(remark: str) -> tuple[str, str, str]:
    text = normalize_text(remark)
    lower = text.lower()

    if 'rte' in lower:
        return 'RTE', 'Fees', 'RTE'

    if 'bus booking' in lower:
        cleaned = re.sub(r'(?i)^bus booking\s*', '', text).strip(' -')
        return 'Bus Booking', 'Bus Booking', cleaned or 'Bus Booking'

    if 'loan' in lower:
        sub_head = 'Other'
        if 'sidh' in lower or 'sid ' in lower:
            sub_head = 'Sidharth'
        elif 'kishor' in lower:
            sub_head = 'Kishor Sir'
        elif 'ashok' in lower:
            sub_head = 'Ashok Sir'
        elif 'sumit' in lower:
            sub_head = 'Sumit Sir'
        return 'Loan', 'Management', sub_head

    return 'Other', 'Other', text[:80] or 'Other'


def iter_real_rows(ws):
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row[1] is None or row[2] is None:
            continue
        yield row


def generate_expense_rows(ws, session_label: str, employee_map: dict[str, int], employee_names: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in iter_real_rows(ws):
        voucher = normalize_text(row[0])
        date = format_date(row[1])
        amount = normalize_amount(row[2])
        remark = normalize_text(row[3])
        name = normalize_text(row[4])
        major_head = normalize_text(row[5])
        head = normalize_text(row[6])
        sub_head = normalize_text(row[7])

        if major_head.lower() == 'salary':
            sub_head = name or sub_head or 'Salary'

        payment_type = infer_payment_type(remark, sub_head)
        emp_no = ''
        if major_head.lower() == 'salary':
            emp_no = match_employee_number(sub_head, employee_map, employee_names)

        rows.append({
            'Emp_No': emp_no,
            'Voucher_Number': voucher,
            'Date': date,
            'Amount': amount,
            'Major_Head': major_head,
            'Head': head,
            'Sub_Head': sub_head,
            'Payment_Type': payment_type,
            'Session': session_label,
            'Details': remark,
        })
    return rows


def generate_fee_income_rows(ws, session_label: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in iter_real_rows(ws):
        voucher = normalize_text(row[0])
        date = format_date(row[1])
        amount = normalize_amount(row[2])
        account_name = normalize_text(row[4])
        fee_type = normalize_text(row[7]) or 'Tuition Fee'
        major_head, head = normalize_fee_head(fee_type)
        details = fee_type

        rows.append({
            'Voucher_Number': voucher,
            'Date': date,
            'Amount': amount,
            'Major_Head': major_head,
            'Head': head,
            'Sub_Head': account_name,
            'Payment_Type': 'Cash',
            'Session': session_label,
            'Details': details,
        })
    return rows


def generate_other_income_rows(ws, session_label: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in iter_real_rows(ws):
        voucher = normalize_text(row[0])
        date = format_date(row[1])
        amount = normalize_amount(row[2])
        remark = normalize_text(row[3])
        major_head, head, sub_head = classify_other_income(remark)

        rows.append({
            'Voucher_Number': voucher,
            'Date': date,
            'Amount': amount,
            'Major_Head': major_head,
            'Head': head,
            'Sub_Head': sub_head,
            'Payment_Type': 'Cash',
            'Session': session_label,
            'Details': remark,
        })
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8-sig') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Generate import-ready ledger CSVs from the accounts workbook.')
    parser.add_argument(
        '--excel',
        default='datamigration/input-accountsExcelFiles/DPS 2025-26 Accounts.xlsm',
        help='Path to the source workbook',
    )
    parser.add_argument(
        '--expense-output',
        default='datamigration/convertedcsvs/expense_2025_26.csv',
        help='Path for the expense CSV output',
    )
    parser.add_argument(
        '--income-output',
        default='datamigration/convertedcsvs/income_2025_26.csv',
        help='Path for the income CSV output',
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    excel_path = ROOT / args.excel
    expense_path = ROOT / args.expense_output
    income_path = ROOT / args.income_output

    if not excel_path.exists():
        sys.exit(f'Workbook not found: {excel_path}')

    session_lookup = build_session_lookup()
    session_label = workbook_session_label(excel_path.name, session_lookup)
    employee_map, employee_names = build_employee_lookup()

    workbook = openpyxl.load_workbook(excel_path, read_only=True, data_only=True, keep_vba=True)

    expense_rows = generate_expense_rows(workbook['VExp'], session_label, employee_map, employee_names)
    income_rows = generate_fee_income_rows(workbook['VIncF'], session_label)
    income_rows.extend(generate_other_income_rows(workbook['VIncO'], session_label))

    write_csv(expense_path, EXPENSE_FIELDS, expense_rows)
    write_csv(income_path, OUTPUT_FIELDS, income_rows)

    print(f'Expense rows written: {len(expense_rows)} -> {expense_path}')
    print(f'Income rows written:  {len(income_rows)} -> {income_path}')
    print(f'Session used: {session_label}')


if __name__ == '__main__':
    main()