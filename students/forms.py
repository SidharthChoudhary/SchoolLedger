from django import forms
from .models import Student, Class, FeesAccount, StudentAccount, FeesAccountAgreement


class BulkImportStudentForm(forms.Form):
    DUPLICATE_CHOICES = [
        ('error', 'Mark as error'),
        ('skip', 'Skip duplicates'),
        ('update', 'Update duplicates'),
    ]

    csv_file = forms.FileField(
        label='CSV File',
        help_text='Upload a CSV file with student data'
    )
    handle_duplicates = forms.ChoiceField(
        choices=DUPLICATE_CHOICES,
        initial='error',
        label='Handle Duplicates',
        help_text='Decide how to handle duplicate student records'
    )
    dry_run = forms.BooleanField(
        required=False,
        initial=False,
        label='Dry Run',
        help_text='Preview changes without saving to database'
    )


class ClassForm(forms.ModelForm):
    class Meta:
        model = Class
        fields = ['class_name', 'class_code', 'age']
        widgets = {
            'class_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Class Name (e.g., Prep, Nursery)'}),
            'class_code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Class Code (max 5 chars)', 'maxlength': '5'}),
            'age': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Age', 'min': '1', 'max': '25'}),
        }


class StudentForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = [
            'first_name', 'last_name', 'date_of_birth', 'gender',
            'fathers_name', 'mothers_name', 'gardians_name',
            'medical_conditions', 'dietary_restrictions',
            'fathers_phone', 'mothers_phone', 'gardians_phone',
            'student_class', 'session', 'transport_method', 'previous_school',
            'srn', 'nic_student_id', 'admission_date', 'rte', 'primary_account_holder', 'fees_account',
            'image'
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'fathers_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Father's Name"}),
            'mothers_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Mother's Name"}),
            'gardians_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': "Guardian's Name"}),
            'medical_conditions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Medical Conditions'}),
            'dietary_restrictions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Dietary Restrictions'}),
            'fathers_phone': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': "Father's Phone Number", 'min': '0'}),
            'mothers_phone': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': "Mother's Phone Number", 'min': '0'}),
            'gardians_phone': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': "Guardian's Phone Number", 'min': '0'}),
            'student_class': forms.Select(attrs={'class': 'form-control'}),
            'session': forms.Select(attrs={'class': 'form-control'}),
            'transport_method': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'previous_school': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Previous School Name'}),
            'srn': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Student Registration Number'}),
            'nic_student_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'NIC Student ID'}),
            'admission_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'rte': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'primary_account_holder': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'fees_account': forms.Select(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }


class FeesAccountForm(forms.ModelForm):
    class Meta:
        model = FeesAccount
        fields = ['name', 'account_open', 'account_status', 'account_close', 'register_page', 'remark']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Name'}),
            'account_open': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'account_status': forms.Select(attrs={'class': 'form-control'}),
            'account_close': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'register_page': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Register Page'}),
            'remark': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Remark (e.g. reason for closing)', 'rows': 2}),
        }


class StudentAccountAgreementForm(forms.ModelForm):
    class Meta:
        model = StudentAccount
        fields = [
            'tuition_fees', 'tc_fees', 'admission_fees',
            'book_set', 'book_diary', 'book_other',
            'uniform_shirt', 'uniform_pant', 'uniform_sweater', 'uniform_hoody', 'uniform_t_shirt',
            'uniform_tie', 'uniform_belt', 'uniform_id_card',
        ]
        widgets = {
            'tuition_fees': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'tc_fees': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'admission_fees': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'book_set': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'book_diary': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'book_other': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'uniform_shirt': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'uniform_pant': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'uniform_sweater': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'uniform_hoody': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'uniform_t_shirt': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'uniform_tie': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'uniform_belt': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'uniform_id_card': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }


class FeesAccountAgreementForm(forms.ModelForm):
    class Meta:
        model = FeesAccountAgreement
        fields = [
            'tuition_fees', 'tc_fees', 'admission_fees',
            'book_set', 'book_diary', 'book_other',
            'uniform_shirt', 'uniform_pant', 'uniform_sweater', 'uniform_hoody', 'uniform_t_shirt',
            'uniform_tie', 'uniform_belt', 'uniform_id_card', 'bus_fees',
        ]
        widgets = {
            'tuition_fees': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'tc_fees': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'admission_fees': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'book_set': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'book_diary': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'book_other': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'uniform_shirt': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'uniform_pant': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'uniform_sweater': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'uniform_hoody': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'uniform_t_shirt': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'uniform_tie': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'uniform_belt': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'uniform_id_card': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'bus_fees': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }
