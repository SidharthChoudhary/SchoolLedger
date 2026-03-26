from datetime import datetime

from django.db import models
from django.db.models import Max


class Employee(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
        ("left", "Left"),
    ]
    GENDER_CHOICES = [
        ("M", "Male"),
        ("F", "Female"),
        ("O", "Other"),
    ]
    
    emp_no = models.PositiveIntegerField(unique=True, editable=False, null=True, blank=True)
    name = models.CharField(max_length=120)
    display_name = models.CharField(max_length=120, blank=True, help_text="Display name (can be duplicate, used for UI only). If blank, name is used.")
    dob = models.DateField(null=True, blank=True)

    contact_number = models.CharField(max_length=30, blank=True)
    address = models.TextField(blank=True)

    qualification = models.CharField(max_length=120, blank=True)
    experience_years = models.DecimalField(max_digits=4, decimal_places=1, default=0)  # e.g. 2.5 yrs
    previous_institute = models.CharField(max_length=150, blank=True)

    post = models.CharField(max_length=120, blank=True)
    joining_date = models.DateField(null=True, blank=True)

    base_salary_per_month = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    leaves_entitled = models.IntegerField(default=0)

    leaving_date = models.DateField(null=True, blank=True)

    emp_image = models.ImageField(upload_to="employees/", null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        blank=True
    )
    role = models.CharField(max_length=80, blank=True)
    role_detail = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-id"]

    def __str__(self):
        return self.name


    def save(self, *args, **kwargs):
        if not self.emp_no:
            last_no = Employee.objects.aggregate(m=Max("emp_no"))["m"] or 999
            self.emp_no = last_no + 1   # first will become 1000
        super().save(*args, **kwargs)


class EmployeeAttendance(models.Model):
    """Track daily employee attendance"""
    ATTENDANCE_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('half-day', 'Half Day'),
        ('leave', 'Leave'),
    ]
    
    session = models.ForeignKey('dailyLedger.Session', on_delete=models.CASCADE, related_name='employee_attendance')
    date = models.DateField()
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='attendance_records')
    attendance = models.CharField(max_length=10, choices=ATTENDANCE_CHOICES, default='present')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', 'employee__name']
        unique_together = ['session', 'date', 'employee']
    
    def __str__(self):
        return f"{self.employee.name} - {self.date} - {self.get_attendance_display()}"


class EmployeePayrollEntry(models.Model):
    """Unified payroll entry — accountant-validated salary per employee per month"""
    session = models.ForeignKey('dailyLedger.Session', on_delete=models.CASCADE, related_name='payroll_entries')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payroll_entries')
    month = models.CharField(max_length=7, help_text="Format: YYYY-MM")
    payable_salary = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Final validated salary")
    old_dues = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    other_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    note = models.TextField(blank=True)
    # Manual override when attendance register is not filled
    manual_work_days = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True, help_text="Override: working days if attendance register not filled")
    manual_leave_days = models.IntegerField(null=True, blank=True, help_text="Override: leave days if attendance register not filled")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['session', 'employee', 'month']
        ordering = ['employee__name']

    def __str__(self):
        return f"{self.employee.name} - {self.month}"