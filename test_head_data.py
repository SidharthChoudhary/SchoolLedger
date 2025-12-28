import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
django.setup()

from dailyLedger.views import _build_head_data

data = _build_head_data()
json_str = json.dumps(data)
print(f"JSON length: {len(json_str)}")
print(f"First 500 chars: {json_str[:500]}")

# Check structure
print("\nStructure check:")
print(f"Keys: {list(data.keys())}")
if 'Expense' in data:
    print(f"Expense major heads: {list(data['Expense'].keys())[:3]}")
    if data['Expense']:
        first_major = list(data['Expense'].keys())[0]
        print(f"  {first_major} heads: {list(data['Expense'][first_major].keys())[:2]}")
