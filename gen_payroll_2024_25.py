import openpyxl, csv

staff = {}
with open(r'c:\LocalFolder\SchoolLedger\datamigration\dps_staffList_29Mar26.csv', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        staff[row['Name'].strip().lower()] = row['Emp_No']
staff['anita bai']     = '1003'
staff['rahuk kumawat'] = '1012'
staff['munsi driver']  = '1014'   # Munshi Khan

MONTH_MAP = {
    'April':'2024-04','May':'2024-05','June':'2024-06',
    'July':'2024-07','August':'2024-08','September':'2024-09',
    'October':'2024-10','November':'2024-11','December':'2024-12',
    'January':'2025-01','February':'2025-02','March':'2025-03',
}
MONTH_COLS = list(MONTH_MAP.keys())

wb = openpyxl.load_workbook(
    r'c:\LocalFolder\SchoolLedger\datamigration\input-accountsExcelFiles\DPS 2024-25_Accounts.xlsm',
    read_only=True, data_only=True)
ws = wb['SdS']
rows = list(ws.iter_rows(values_only=True))
header = rows[0]
col_idx = {str(h).strip(): i for i, h in enumerate(header) if h}

out_rows  = []
unmatched = []

for r in rows[1:]:
    name = (r[col_idx['Name']] or '').strip()
    if not name:
        continue
    old_dues = float(r[col_idx['Old Dues']] or 0)
    name_key = name.lower()
    emp_id = staff.get(name_key, '')
    if not emp_id:
        unmatched.append(name)
        continue

    # Collect months that have a value (None = skip, but 0 is kept)
    month_rows = []
    for month_name in MONTH_COLS:
        if month_name not in col_idx:
            continue
        val = r[col_idx[month_name]]
        if val is not None:
            month_rows.append((MONTH_MAP[month_name], float(val)))

    if month_rows:
        # Normal case: write one row per month, old_dues on first month
        for i, (month_str, payable) in enumerate(month_rows):
            out_rows.append({
                'Emp_ID'           : emp_id,
                'Month'            : month_str,
                'Payable_Salary'   : payable,
                'Old_Dues'         : old_dues if i == 0 else 0.0,
                'Other_Amount'     : 0,
                'Note'             : '',
                'Manual_Work_Days' : '',
                'Manual_Leave_Days': '',
            })
    elif old_dues != 0:
        # Employee left / no monthly salary — but still has dues to carry
        # Record a single April row with 0 payable and the dues
        out_rows.append({
            'Emp_ID'           : emp_id,
            'Month'            : '2024-04',
            'Payable_Salary'   : 0.0,
            'Old_Dues'         : old_dues,
            'Other_Amount'     : 0,
            'Note'             : 'Dues carried forward',
            'Manual_Work_Days' : '',
            'Manual_Leave_Days': '',
        })
    # If months=0 AND old_dues=0, skip entirely (nothing to record)

out_path = r'c:\LocalFolder\SchoolLedger\datamigration\convertedcsvs\payroll_2024_25.csv'
fieldnames = ['Emp_ID','Month','Payable_Salary','Old_Dues','Other_Amount','Note','Manual_Work_Days','Manual_Leave_Days']
with open(out_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    w.writerows(out_rows)

print(f'Written {len(out_rows)} rows to payroll_2024_25.csv')
if unmatched:
    print('Skipped (unmatched names):', unmatched)
else:
    print('All names matched OK')
