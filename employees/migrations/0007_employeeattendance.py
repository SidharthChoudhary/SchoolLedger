# Generated migration for EmployeeAttendance model

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('employees', '0006_employeeregister_payable_salary'),
        ('dailyLedger', '0007_session'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmployeeAttendance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('attendance', models.CharField(choices=[('present', 'Present'), ('absent', 'Absent'), ('half-day', 'Half Day'), ('leave', 'Leave')], default='present', max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('employee', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attendance_records', to='employees.employee')),
                ('session', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='employee_attendance', to='dailyLedger.session')),
            ],
            options={
                'ordering': ['-date', 'employee__name'],
                'unique_together': {('session', 'date', 'employee')},
            },
        ),
    ]
