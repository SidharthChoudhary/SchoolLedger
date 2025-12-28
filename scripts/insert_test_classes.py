import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
django.setup()

from students.models import Class

# Test classes data
classes_data = [
    {'class_name': 'Prep', 'age': 3},
    {'class_name': 'Nursery', 'age': 4},
    {'class_name': 'KG', 'age': 5},
    {'class_name': 'Class 1', 'age': 6},
    {'class_name': 'Class 2', 'age': 7},
    {'class_name': 'Class 3', 'age': 8},
    {'class_name': 'Class 4', 'age': 9},
    {'class_name': 'Class 5', 'age': 10},
]

# Insert classes
for class_data in classes_data:
    class_obj, created = Class.objects.get_or_create(
        class_name=class_data['class_name'],
        defaults={'age': class_data['age']}
    )
    if created:
        print(f"✓ Created: {class_obj.class_name} (Age: {class_obj.age})")
    else:
        print(f"- Already exists: {class_obj.class_name}")

print("\nAll classes inserted successfully!")
