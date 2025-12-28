import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
django.setup()

from dailyLedger.models import Expense

# Delete all Expense records
count = Expense.objects.count()
Expense.objects.all().delete()

print(f'Truncated Expense table: deleted {count} records')
