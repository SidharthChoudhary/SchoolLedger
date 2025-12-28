from datetime import datetime

from django.db import models
from django.db.models import Max


class EmployeeRegister(models.Model):
    """Track employee attendance and paid days for salary calculation"""
    session = models.ForeignKey('dailyLedger.Session', on_delete=models.CASCADE)
    employee = models.ForeignKey('Employee', on_delete=models.CASCADE)
    month = models.CharField(max_length=7, default="2024-01", help_text="Format: YYYY-MM (e.g., 2024-01)")
    paid_days = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Number of days to be paid")
    payable_salary = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Calculated monthly payable salary")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-session", "-month", "employee__name"]
        unique_together = ["session", "employee", "month"]

    def __str__(self):
        return f"{self.employee.name} - {self.session.session} - {self.month} ({self.paid_days} days)"

    @property
    def month_display(self):
        try:
            return datetime.strptime(self.month, "%Y-%m").strftime("%B %Y")
        except (ValueError, TypeError):
            return self.month

    def save(self, *args, **kwargs):
        """Calculate payable salary based on paid_days and employee's entitled leaves"""
        if self.employee:
            base_salary = self.employee.base_salary_per_month or 0
            entitled_leaves = self.employee.leaves_entitled or 0
            paid_days = self.paid_days or 0
            
            # If paid_days >= (30 - entitled_leaves), pay full salary
            # Otherwise, pro-rata: paid_days * (base_salary / 30)
            min_work_days = 30 - entitled_leaves
            
            if paid_days >= min_work_days:
                self.payable_salary = base_salary
            else:
                self.payable_salary = (paid_days * base_salary) / 30
        
        super().save(*args, **kwargs)


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


class ManualSalaryData(models.Model):
    """Track manual salary data for old dues or adjustments"""
    AMOUNT_TYPE_CHOICES = [
        ('salary', 'Salary'),
        ('old_due', 'Old Due'),
        ('other', 'Other'),
    ]
    
    session = models.ForeignKey('dailyLedger.Session', on_delete=models.CASCADE, related_name='manual_salary_data')
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='manual_salary_records')
    amount_type = models.CharField(max_length=20, choices=AMOUNT_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Amount in rupees")
    month = models.CharField(max_length=7, help_text="Format: YYYY-MM (e.g., 2024-01)")
    note = models.TextField(blank=True, help_text="Optional notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-session', '-month', 'employee__name']
        verbose_name_plural = "Manual Salary Data"
    
    def __str__(self):
        return f"{self.employee.name} - {self.month} - {self.get_amount_type_display()}"