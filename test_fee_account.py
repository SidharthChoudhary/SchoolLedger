#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
django.setup()

from students.models import Student, FeesAccount

# Check the student with SRN 5613
try:
    student = Student.objects.get(srn='5613')
    print(f"✓ Found student: {student.first_name} {student.last_name}")
    print(f"  SRN: {student.srn}")
    print(f"  Fees Account FK: {student.fees_account}")
    print(f"  Fees Account ID: {student.fees_account.id if student.fees_account else 'None'}")
    
    if student.fees_account:
        print(f"  Account Name: {student.fees_account.account_name}")
        print(f"  Account ID: {student.fees_account.account_id}")
    else:
        print("  ⚠️ No fee account assigned!")
        print("\nAvailable fee accounts:")
        for fa in FeesAccount.objects.all():
            print(f"  - {fa.id}: {fa.account_name} (ID: {fa.account_id})")
        
except Student.DoesNotExist:
    print(f"✗ Student with SRN 5613 not found")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
