#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
django.setup()

from dailyLedger.models import Session
from students.models import SessionClassStudentMap, Class

# Test with session ID 1
try:
    session = Session.objects.get(id=1)
    print(f"✓ Found session: {session}")
    
    # Get distinct class IDs
    class_ids = SessionClassStudentMap.objects.filter(session=session).values_list('student_class_id', flat=True).distinct()
    print(f"✓ Class IDs: {list(class_ids)}")
    
    # Get the actual Class objects
    classes = Class.objects.filter(id__in=class_ids)
    print(f"✓ Classes: {list(classes)}")
    
    class_list = [{'id': c.id, 'name': c.class_code} for c in classes]
    print(f"✓ Class list: {class_list}")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
