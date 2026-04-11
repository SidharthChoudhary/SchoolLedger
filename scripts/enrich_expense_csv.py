"""
Adds Emp_No column to expense_2024_25.csv by matching Sub_Head names to employees in DB.
Output: expense_2024_25_with_empid.csv
"""
import os, sys, django, csv, difflib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
django.setup()

from employees.models import Employee

emp_map   = {e.name.strip().lower(): e.emp_no for e in Employee.objects.all()}
emp_names = list(emp_map.keys())

in_path  = os.path.join('datamigration', 'convertedcsvs', 'expense_2024_25.csv')
out_path = os.path.join('datamigration', 'convertedcsvs', 'expense_2024_25_with_empid.csv')

unmatched = []

with open(in_path, encoding='utf-8-sig') as fin, \
     open(out_path, 'w', newline='', encoding='utf-8') as fout:

    reader = csv.DictReader(fin)
    fieldnames = ['Emp_No'] + reader.fieldnames
    writer = csv.DictWriter(fout, fieldnames=fieldnames)
    writer.writeheader()

    for row in reader:
        sub_head   = row.get('Sub_Head', '').strip()
        major_head = row.get('Major_Head', '').lower()
        head       = row.get('Head', '').lower()
        emp_no     = ''

        if 'salary' in major_head or 'salary' in head:
            key = sub_head.lower()
            if key in emp_map:
                emp_no = emp_map[key]
            else:
                matches = difflib.get_close_matches(key, emp_names, n=1, cutoff=0.6)
                if matches:
                    emp_no = emp_map[matches[0]]
                    print(f'  FUZZY: "{sub_head}" -> "{matches[0]}" (ID {emp_no})')
                else:
                    unmatched.append(sub_head)

        row['Emp_No'] = emp_no
        writer.writerow(row)

print(f'\nWritten: {out_path}')
if unmatched:
    print(f'Unmatched (Emp_No left blank):')
    for n in sorted(set(unmatched)):
        print(f'  {n}')
else:
    print('All salary rows matched successfully.')
