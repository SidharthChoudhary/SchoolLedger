#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
django.setup()

from dailyLedger.models import Expense

# Truncate the Expense table
count = Expense.objects.count()
Expense.objects.all().delete()
print(f"Deleted {count} expense records")
