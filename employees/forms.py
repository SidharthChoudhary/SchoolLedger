from django import forms
from .models import Employee, EmployeeAttendance
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

