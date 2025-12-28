#!/usr/bin/env python
"""
Script to clean/truncate the Income table
Run with: python manage.py shell < truncate_income.py
"""

from dailyLedger.models import Income

# Delete all income records
deleted_count, _ = Income.objects.all().delete()
print(f"Deleted {deleted_count} income records from the database.")
