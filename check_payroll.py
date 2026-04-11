import openpyxl, csv

staff = {}
with open(r'c:\LocalFolder\SchoolLedger\datamigration\dps_staffList_29Mar26.csv', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        staff[row['Name'].strip().lower()] = row['Emp_No']
staff['anita bai']     = '1003'
staff['rahuk kumawat'] = '1012'
staff['munsi driver']  = '1014'

wb = openpyxl.load_workbook(
    r'c:\LocalFolder\SchoolLedger\datamigration\input-accountsExcelFiles\DPS 2024-25_Accounts.xlsm',
    read_only=True, data_only=True)
ws = wb['SdS']
rows = list(ws.iter_rows(values_only=True))
header = rows[0]
print('Header cols:', [(i, h) for i, h in enumerate(header) if h])
print()

MONTHS = ['April','May','June','July','August','September','October','November','December','January','February','March']
col_idx = {str(h).strip(): i for i, h in enumerate(header) if h}

print(f'Total data rows in SdS: {len(rows)-1}')
total_month_cells = 0
print()

for r in rows[1:]:
    name_col = col_idx.get('Name', 0)
    name = (r[name_col] or '').strip()
    if not name:
        continue
    old_dues = r[col_idx.get('Old Dues', 6)] or 0
    months_with_data = []
    for m in MONTHS:
        if m in col_idx:
            val = r[col_idx[m]]
            if val is not None:
                months_with_data.append(m)
                total_month_cells += 1
    emp_id = staff.get(name.lower(), '???')
    print(f'  [{emp_id:>6}] {name:<35} old_dues={old_dues:>8}  months={len(months_with_data):>2}  {months_with_data}')

print()
print(f'Total month-cells (expected rows in CSV): {total_month_cells}')
