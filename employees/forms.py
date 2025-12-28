from django import forms
from .models import Employee, EmployeeRegister, EmployeeAttendance
from dailyLedger.models import Session


class BulkImportEmployeeForm(forms.Form):
    DUPLICATE_CHOICES = [
        ('error', 'Mark as error'),
        ('skip', 'Skip duplicates'),
        ('update', 'Update duplicates'),
    ]
    
    csv_file = forms.FileField(
        label="CSV File",
        help_text="Upload a CSV file with employee data"
    )
    handle_duplicates = forms.ChoiceField(
        choices=DUPLICATE_CHOICES,
        initial='error',
        label="Handle Duplicates",
        help_text="Decide how to handle duplicate records"
    )
    dry_run = forms.BooleanField(
        required=False,
        initial=False,
        label="Dry Run",
        help_text="Check this to preview data without importing"
    )


class EmployeeRegisterForm(forms.ModelForm):
    payable_salary = forms.DecimalField(
        label="Payable Salary",
        required=False,
        disabled=True,
        widget=forms.NumberInput(attrs={"class": "form-control", "readonly": "readonly"})
    )
    
    class Meta:
        model = EmployeeRegister
        fields = ["session", "employee", "month", "paid_days", "payable_salary"]
        widgets = {
            "session": forms.Select(attrs={"class": "form-control"}),
            "employee": forms.Select(attrs={"class": "form-control"}),
            "month": forms.DateInput(attrs={"type": "month", "class": "form-control"}),
            "paid_days": forms.NumberInput(attrs={"class": "form-control", "step": "0.5", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default session to Active
        if not self.instance.pk:
            active_session = Session.objects.filter(status="Active").first()
            if active_session:
                self.initial["session"] = active_session.pk
            # Set default month to current year-month (YYYY-MM)
            try:
                from datetime import date
                self.initial["month"] = date.today().strftime("%Y-%m")
            except Exception:
                pass
        
        # Filter employees to exclude inactive status
        self.fields["employee"].queryset = Employee.objects.exclude(status="inactive").order_by("name")


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = [
            "name", "dob", "contact_number", "gender",
            "qualification", "address",
            "experience_years", "previous_institute",
            "post", "role", "role_detail",
            "joining_date", "base_salary_per_month",
            "status", "leaves_entitled", "leaving_date",
            "emp_image",
        ]
        widgets = {
            "dob": forms.DateInput(attrs={"type": "date"}),
            "joining_date": forms.DateInput(attrs={"type": "date"}),
            "leaving_date": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 2}),
            "role_detail": forms.TextInput(attrs={"placeholder": "e.g. Class Teacher – 5A"}),
        }

class EmployeeAttendanceForm(forms.ModelForm):
    class Meta:
        model = EmployeeAttendance
        fields = ['session', 'date', 'employee', 'attendance']
        widgets = {
            'session': forms.Select(attrs={'class': 'form-control'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'employee': forms.Select(attrs={'class': 'form-control'}),
            'attendance': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter employees to only active ones
        self.fields['employee'].queryset = Employee.objects.filter(status='active').order_by('name')


class ManualSalaryDataForm(forms.ModelForm):
    class Meta:
        from .models import ManualSalaryData
        model = ManualSalaryData
        fields = ['session', 'employee', 'amount_type', 'amount', 'month', 'note']
        widgets = {
            'session': forms.Select(attrs={'class': 'form-control'}),
            'employee': forms.Select(attrs={'class': 'form-control'}),
            'amount_type': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'month': forms.DateInput(attrs={'type': 'month', 'class': 'form-control'}),
            'note': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default session to current session
        if not self.instance.pk:
            current_session = Session.objects.filter(status='current_session').first()
            if current_session:
                self.initial['session'] = current_session.pk
        # Filter employees
        self.fields['employee'].queryset = Employee.objects.filter(status='active').order_by('name')


class BulkImportManualSalaryDataForm(forms.Form):
    DUPLICATE_CHOICES = [
        ('error', 'Mark as error'),
        ('skip', 'Skip duplicates'),
        ('update', 'Update duplicates'),
    ]
    
    csv_file = forms.FileField(
        label="CSV File",
        help_text="Upload a CSV file with manual salary data"
    )
    handle_duplicates = forms.ChoiceField(
        choices=DUPLICATE_CHOICES,
        initial='error',
        label="Handle Duplicates",
        help_text="Decide how to handle duplicate records"
    )
    dry_run = forms.BooleanField(
        required=False,
        initial=False,
        label="Dry Run",
        help_text="Check this to preview data without importing"
    )