import django
import os

os.environ['DJANGO_SETTINGS_MODULE'] = 'schoolapp.settings'
django.setup()

from students.models import Class

lines = []
lines.append("-- Class INSERT SQL for PythonAnywhere")
lines.append("")
lines.append("DELETE FROM students_class;")
lines.append("")

for c in Class.objects.all().order_by('age'):
    name = c.class_name.replace("'", "''")
    code = (c.class_code or '').replace("'", "''")
    lines.append(
        f"INSERT INTO students_class (id, class_name, class_code, age, created_at, updated_at) "
        f"VALUES ({c.id}, '{name}', '{code}', {c.age}, NOW(), NOW());"
    )

lines.append("")
lines.append("-- Reset auto-increment sequence")
lines.append("ALTER TABLE students_class AUTO_INCREMENT = 100;")

print('\n'.join(lines))
