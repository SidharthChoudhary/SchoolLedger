from django import forms
from datetime import date as dt_date
from .models import Expense, Income, Head, Session, FeesStructure
from employees.models import Employee
from students.models import FeesAccount

class LedgerEntryFormBase(forms.ModelForm):
    """Base form for Expense and Income entries"""
    
    # Store ledger_type to use in __init__
    ledger_type_value = "Expense"
    
    def __init__(self, *args, ledger_type="Expense", **kwargs):
        super().__init__(*args, **kwargs)
        self.ledger_type_value = ledger_type
        
        # Filter heads by ledger_type
        filtered_heads = Head.objects.filter(ledger_type=ledger_type)
        
        # Get unique values from the filtered heads
        majors_set = filtered_heads.values_list("major_head", flat=True).distinct().order_by("major_head")
        majors = [("", "---")] + [(m, m) for m in majors_set]
        
        heads_set = filtered_heads.values_list("head", flat=True).distinct().order_by("head")
        heads = [("", "---")] + [(h, h) for h in heads_set]
        
        subs_set = filtered_heads.filter(sub_head__isnull=False).values_list("sub_head", flat=True).distinct().order_by("sub_head")
        subs = [("", "---")] + [(s, s) for s in subs_set]

        self.fields["major_head"] = forms.ChoiceField(choices=majors, required=False)
        self.fields["head"] = forms.ChoiceField(choices=heads, required=False)
        self.fields["sub_head"] = forms.ChoiceField(choices=subs, required=False)

    class Meta:
        fields = [
            'voucher_number',
            'date',
            'amount',
            'details',
            'session',
            'major_head',
            'head',
            'sub_head',
            'payment_type',
        ]
        widgets = {
            'voucher_number': forms.TextInput(attrs={'autofocus': 'autofocus'}),
            "date": forms.DateInput(attrs={"type": "date"}),
            "details": forms.TextInput(),
        }

class ExpenseForm(LedgerEntryFormBase):
    class Meta(LedgerEntryFormBase.Meta):
        model = Expense

class IncomeForm(LedgerEntryFormBase):
    def __init__(self, *args, ledger_type="Income", **kwargs):
        super().__init__(*args, ledger_type=ledger_type, **kwargs)
        
        # Remove payment_type field - not relevant for income
        if "payment_type" in self.fields:
            del self.fields["payment_type"]
        
        # Set date default to today
        if 'date' in self.fields:
            self.fields['date'].initial = dt_date.today()
    
    class Meta(LedgerEntryFormBase.Meta):
        model = Income
        fields = ['session', 'major_head', 'head', 'sub_head', 'voucher_number', 'date', 'amount', 'details']


class IncomeFeesForm(forms.ModelForm):
    """Separate form for fee-based income entry"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Filter heads by ledger_type = Income
        filtered_heads = Head.objects.filter(ledger_type='Income', status='Active')
        
        majors_set = filtered_heads.values_list("major_head", flat=True).distinct().order_by("major_head")
        majors = [("", "---")] + [(m, m) for m in majors_set]
        
        heads_set = filtered_heads.values_list("head", flat=True).distinct().order_by("head")
        heads = [("", "---")] + [(h, h) for h in heads_set]
        
        subs_set = filtered_heads.filter(sub_head__isnull=False).values_list("sub_head", flat=True).distinct().order_by("sub_head")
        subs = [("", "---")] + [(s, s) for s in subs_set]

        self.fields["major_head"] = forms.ChoiceField(choices=majors, required=True)
        self.fields["head"] = forms.ChoiceField(choices=heads, required=True)
        self.fields["sub_head"] = forms.ChoiceField(choices=subs, required=False)
        
        # Remove "Against Credit" from payment_type choices for income
        if "payment_type" in self.fields:
            current_payment_choices = self.fields["payment_type"].choices
            filtered_payment_choices = [choice for choice in current_payment_choices if choice[0] != "Against Credit"]
            self.fields["payment_type"].choices = filtered_payment_choices
        
        # Set date default to today
        if 'date' in self.fields:
            self.fields['date'].initial = dt_date.today()

    class Meta:
        model = Income
        fields = [
            'voucher_number',
            'date',
            'amount',
            'details',
            'session',
            'major_head',
            'head',
            'sub_head',
            'fees_account',
        ]
        widgets = {
            'voucher_number': forms.TextInput(attrs={'autofocus': 'autofocus'}),
            "date": forms.DateInput(attrs={"type": "date"}),
            "details": forms.TextInput(),
            'session': forms.Select(attrs={'id': 'session-select', 'style': 'height: 40px;'}),
            'fees_account': forms.HiddenInput(),
        }


class HeadForm(forms.ModelForm):
    class Meta:
        model = Head
        fields = ["major_head", "head", "sub_head", "details", "ledger_type", "status"]
        widgets = {
            "major_head": forms.TextInput(attrs={"placeholder": "e.g. Salary"}),
            "head": forms.TextInput(attrs={"placeholder": "e.g. Daily run"}),
            "sub_head": forms.TextInput(attrs={"placeholder": "e.g. Other"}),
            "details": forms.Textarea(attrs={"rows": 3, "placeholder": "Optional: Add any additional details or notes"}),
        }


class SessionForm(forms.ModelForm):
    class Meta:
        model = Session
        fields = ["session", "status"]
        widgets = {
            "session": forms.TextInput(attrs={"placeholder": "e.g. 2025-26"}),
        }


class BulkImportForm(forms.Form):
    csv_file = forms.FileField(
        label="Upload CSV File",
        help_text="Max file size: 5MB. Format: Ledger_Type, Major_Head, Head, Sub_Head, Status (optional), Details (optional)",
        widget=forms.FileInput(attrs={
            'accept': '.csv',
            'class': 'form-control',
            'style': 'height:40px;'
        })
    )
    import_type = forms.ChoiceField(
        label="Import Type",
        choices=[
            ('heads', 'Account Heads'),
        ],
        initial='heads',
        widget=forms.RadioSelect(attrs={'class': 'radiolist'})
    )
    handle_duplicates = forms.ChoiceField(
        label="If duplicate exists",
        choices=[
            ('skip', 'Skip this row'),
            ('update', 'Update existing record'),
            ('error', 'Treat as error'),
        ],
        initial='error',
        widget=forms.RadioSelect(attrs={'class': 'radiolist'})
    )
    dry_run = forms.BooleanField(
        label="Dry run (preview only, don't save)",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'style': 'width: 20px; height: 20px; cursor: pointer;'
        })
    )


class FeesStructureForm(forms.ModelForm):
    class Meta:
        model = FeesStructure
        fields = [
            'session', 'class_code',
            'fee_tuition', 'fee_tc', 'fee_admission',
            'book_set', 'book_diary', 'book_other',
            'uniform_shirt', 'uniform_pant', 'uniform_tie', 'uniform_belt', 'uniform_id_card'
        ]
        widgets = {
            'session': forms.Select(attrs={'class': 'form-control'}),
            'class_code': forms.Select(attrs={'class': 'form-control'}),
            'fee_tuition': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'maxlength': '6'}),
            'fee_tc': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'maxlength': '6'}),
            'fee_admission': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'maxlength': '6'}),
            'book_set': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'maxlength': '6'}),
            'book_diary': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'maxlength': '6'}),
            'book_other': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'maxlength': '6'}),
            'uniform_shirt': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'maxlength': '6'}),
            'uniform_pant': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'maxlength': '6'}),
            'uniform_tie': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'maxlength': '6'}),
            'uniform_belt': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'maxlength': '6'}),
            'uniform_id_card': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'maxlength': '6'}),
        }

class BulkImportLedgerForm(forms.Form):
    csv_file = forms.FileField(
        label="Upload CSV File",
        help_text="Max file size: 5MB. Columns: Voucher_Number, Date, Amount, Major_Head, Head, Sub_Head, Payment_Type, Session, Details",
        widget=forms.FileInput(attrs={
            'accept': '.csv',
            'class': 'form-control',
            'style': 'height:40px;'
        })
    )
    handle_duplicates = forms.ChoiceField(
        label="If duplicate exists",
        choices=[
            ('skip', 'Skip this row'),
            ('update', 'Update existing record'),
            ('error', 'Treat as error'),
        ],
        initial='error',
        widget=forms.RadioSelect(attrs={'class': 'radiolist'})
    )
    dry_run = forms.BooleanField(
        label="Dry run (preview only, don't save)",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'style': 'width: 20px; height: 20px; cursor: pointer;'
        })
    )
