#!/usr/bin/env python
"""
Script to insert 5 test employees into the database
Run from the project root: python scripts/insert_test_employees.py
"""

import os
import sys
import django
from datetime import date

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
django.setup()

from employees.models import Employee


def create_test_employees():
    """Create 5 test employees"""
    employees_data = [
        {
            'name': 'Rajesh Kumar',
            'dob': date(1985, 6, 15),
            'contact_number': '9876543210',
            'gender': 'male',
            'qualification': 'B.Tech',
            'address': '123 Main Street, City',
            'post': 'Teacher',
            'joining_date': date(2020, 1, 1),
            'base_salary_per_month': 25000,
            'status': 'active',
        },
        {
            'name': 'Priya Singh',
            'dob': date(1990, 3, 22),
            'contact_number': '8765432109',
            'gender': 'female',
            'qualification': 'M.A',
            'address': '456 Oak Avenue, City',
            'post': 'Teacher',
            'joining_date': date(2019, 6, 15),
            'base_salary_per_month': 23000,
            'status': 'active',
        },
        {
            'name': 'Anil Patel',
            'dob': date(1988, 11, 30),
            'contact_number': '7654321098',
            'gender': 'male',
            'qualification': 'B.A',
            'address': '789 Pine Road, City',
            'post': 'Administrator',
            'joining_date': date(2021, 2, 1),
            'base_salary_per_month': 20000,
            'status': 'active',
        },
        {
            'name': 'Sneha Sharma',
            'dob': date(1992, 5, 10),
            'contact_number': '6543210987',
            'gender': 'female',
            'qualification': 'B.Sc',
            'address': '321 Elm Street, City',
            'post': 'Teacher',
            'joining_date': date(2022, 1, 10),
            'base_salary_per_month': 22000,
            'status': 'active',
        },
        {
            'name': 'Vikas Joshi',
            'dob': date(1987, 9, 18),
            'contact_number': '5432109876',
            'gender': 'male',
            'qualification': 'B.Com',
            'address': '654 Maple Drive, City',
            'post': 'Accountant',
            'joining_date': date(2018, 7, 15),
            'base_salary_per_month': 18000,
            'status': 'active',
        },
    ]

    print("Creating test employees...\n")
    for emp_data in employees_data:
        emp = Employee.objects.create(**emp_data)
        print(f"✓ Created: {emp.name} (ID: {emp.id})")

    total = Employee.objects.count()
    print(f"\n✓ Total employees in database: {total}")
    print("\nTest employees inserted successfully!")


if __name__ == '__main__':
    try:
        create_test_employees()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
