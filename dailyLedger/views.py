from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum
from django.contrib import messages
from django.http import HttpResponse
import calendar
from datetime import date as dt_date
import json
import csv
from io import StringIO
from accounts.decorators import role_required

from .models import Expense, Income, Session, Head, FeesStructure
from .forms import ExpenseForm, IncomeForm, IncomeFeesForm, HeadForm, SessionForm, BulkImportForm, FeesStructureForm
from .utils import parse_csv_account_heads, import_account_heads, parse_csv_ledger_entries, import_ledger_entries
from .forms import BulkImportLedgerForm
from employees.models import Employee


def _build_head_data():
    """Build head data grouped by ledger_type: {ledger_type: {major: {head: [subs]}}}"""
    result = {}
    
    # Single query to fetch all ACTIVE Head records only
    all_heads = Head.objects.filter(status='Active').values_list("ledger_type", "major_head", "head", "sub_head")
    
    for ledger_type in ["Expense", "Income"]:
        result[ledger_type] = {}
    
    # Process in single pass
    for ledger_type, major_head, head, sub_head in all_heads:
        if ledger_type not in result:
            result[ledger_type] = {}
        if major_head not in result[ledger_type]:
            result[ledger_type][major_head] = {}
        if head not in result[ledger_type][major_head]:
            result[ledger_type][major_head][head] = []
        if sub_head and sub_head not in result[ledger_type][major_head][head]:
            result[ledger_type][major_head][head].append(sub_head)
    
    # Sort the sub_heads for each head
    for ledger_type in result:
        for major_head in result[ledger_type]:
            for head in result[ledger_type][major_head]:
                result[ledger_type][major_head][head].sort()
    
    return json.dumps(result)


def _build_filter_head_data():
    """Build head data for the FILTER form from actual DB records (not Head model).
    This ensures the filter dropdowns reflect what is really stored."""
    result = {"Expense": {}, "Income": {}}

    for major, head, sub in Expense.objects.exclude(
            major_head='').values_list('major_head', 'head', 'sub_head').distinct().order_by(
            'major_head', 'head', 'sub_head'):
        result["Expense"].setdefault(major, {}).setdefault(head, [])
        if sub and sub not in result["Expense"][major][head]:
            result["Expense"][major][head].append(sub)

    for major, head, sub in Income.objects.exclude(
            major_head='').values_list('major_head', 'head', 'sub_head').distinct().order_by(
            'major_head', 'head', 'sub_head'):
        result["Income"].setdefault(major, {}).setdefault(head, [])
        if sub and sub not in result["Income"][major][head]:
            result["Income"][major][head].append(sub)

    return json.dumps(result)



from django.views.decorators.cache import never_cache


def _parse_fy_label(fy_label):
    """Parse financial year label like 2025-2026 and return start/end years."""
    if not fy_label or '-' not in fy_label:
        return None, None
    try:
        start_str, end_str = fy_label.split('-', 1)
        start_year = int(start_str)
        end_year = int(end_str)
    except ValueError:
        return None, None

    if end_year != start_year + 1:
        return None, None
    return start_year, end_year


def _fy_label_from_date(date_value):
    """Return FY label in YYYY-YYYY format for a given date."""
    start_year = date_value.year if date_value.month >= 4 else date_value.year - 1
    return f"{start_year}-{start_year + 1}"


def _build_monthly_ledger_report_data(selected_session_id=None, selected_fy=None):
    """Build report rows and totals for Monthly Ledger Report."""
    sessions = Session.objects.all().order_by('session')
    selected_session = None

    if selected_session_id:
        try:
            selected_session = Session.objects.get(id=selected_session_id)
        except Session.DoesNotExist:
            selected_session = None
            selected_session_id = None
    else:
        selected_session = Session.objects.filter(status='current_session').order_by('-id').first()
        selected_session_id = str(selected_session.id) if selected_session else None

    income_qs = Income.objects.all()
    expense_qs = Expense.objects.all()

    if selected_session_id:
        income_qs = income_qs.filter(session_id=selected_session_id)
        expense_qs = expense_qs.filter(session_id=selected_session_id)

    fy_set = set()
    for d in income_qs.values_list('date', flat=True):
        if d:
            fy_set.add(_fy_label_from_date(d))
    for d in expense_qs.values_list('date', flat=True):
        if d:
            fy_set.add(_fy_label_from_date(d))

    fy_options = sorted(fy_set, key=lambda x: int(x.split('-')[0]), reverse=True)

    session_fy = None
    if selected_session and selected_session.session:
        fy_start_guess, fy_end_guess = _parse_fy_label(selected_session.session)
        if fy_start_guess and fy_end_guess:
            session_fy = selected_session.session

    if not selected_fy and session_fy:
        selected_fy = session_fy

    if selected_fy not in fy_options:
        current_fy = _fy_label_from_date(dt_date.today())
        if current_fy in fy_options:
            selected_fy = current_fy
        elif fy_options:
            selected_fy = fy_options[0]
        elif session_fy:
            selected_fy = session_fy
        else:
            selected_fy = current_fy

    fy_start, fy_end = _parse_fy_label(selected_fy)
    report_rows = []
    income_major_heads = []
    expense_major_heads = []

    totals = {
        'total_income': 0.0,
        'total_expense': 0.0,
        'balance': 0.0,
    }
    income_head_totals = {}
    expense_head_totals = {}

    if selected_session_id:
        # Collect all distinct major heads for this session (no date range filter — must match session report)
        income_major_heads = list(
            income_qs.values_list('major_head', flat=True).distinct().order_by('major_head')
        )
        income_major_heads = [head for head in income_major_heads if head]

        expense_major_heads = list(
            expense_qs.values_list('major_head', flat=True).distinct().order_by('major_head')
        )
        expense_major_heads = [head for head in expense_major_heads if head]

        income_head_totals = {head: 0.0 for head in income_major_heads}
        expense_head_totals = {head: 0.0 for head in expense_major_heads}

        # Get all months that actually have data in this session (same as session_ledger_report)
        income_months = income_qs.dates('date', 'month', order='ASC')
        expense_months = expense_qs.dates('date', 'month', order='ASC')
        all_months = sorted(
            set(list(income_months) + list(expense_months)),
            key=lambda d: (d.year if d.month >= 4 else d.year - 1, (d.month - 4) % 12)
        )

        for month_date in all_months:
            monthly_income = income_qs.filter(date__year=month_date.year, date__month=month_date.month)
            monthly_expense = expense_qs.filter(date__year=month_date.year, date__month=month_date.month)

            income_amounts = []
            expense_amounts = []
            total_income = 0.0
            total_expense = 0.0

            for head in income_major_heads:
                amount = float(monthly_income.filter(major_head=head).aggregate(total=Sum('amount'))['total'] or 0)
                income_amounts.append(amount)
                total_income += amount
                income_head_totals[head] += amount

            for head in expense_major_heads:
                amount = float(monthly_expense.filter(major_head=head).aggregate(total=Sum('amount'))['total'] or 0)
                expense_amounts.append(amount)
                total_expense += amount
                expense_head_totals[head] += amount

            balance = total_income - total_expense

            row = {
                'month_num': month_date.month,
                'month': month_date.strftime('%b %Y'),
                'income_amounts': income_amounts,
                'expense_amounts': expense_amounts,
                'total_income': total_income,
                'total_expense': total_expense,
                'balance': balance,
            }
            report_rows.append(row)

            totals['total_income'] += total_income
            totals['total_expense'] += total_expense
            totals['balance'] += balance

    income_head_totals_list = [income_head_totals[head] for head in income_major_heads]
    expense_head_totals_list = [expense_head_totals[head] for head in expense_major_heads]

    return {
        'sessions': sessions,
        'selected_session': selected_session,
        'selected_session_id': str(selected_session_id) if selected_session_id else '',
        'fy_options': fy_options,
        'selected_fy': selected_fy,
        'income_major_heads': income_major_heads,
        'expense_major_heads': expense_major_heads,
        'income_head_totals_list': income_head_totals_list,
        'expense_head_totals_list': expense_head_totals_list,
        'report_rows': report_rows,
        'totals': totals,
    }

@never_cache
def _ledger_view(request, model, form_class, template_name, page_title, ledger_type="Expense"):
    """Generic ledger view for Expense and Income"""
    edit_id = request.GET.get("edit")
    editing_entry = None
    if edit_id:
        editing_entry = get_object_or_404(model, pk=edit_id)

    if request.method == "POST":
        entry_id = request.POST.get("entry_id")
        if entry_id:
            entry = get_object_or_404(model, pk=entry_id)
            form = form_class(request.POST, instance=entry, ledger_type=ledger_type)
        else:
            form = form_class(request.POST, ledger_type=ledger_type)

        if form.is_valid():
            form.save()
            from django.urls import reverse
            base_url = reverse(request.resolver_match.url_name)
            query_string = request.GET.urlencode()
            return redirect(f"{base_url}?{query_string}" if query_string else base_url)
    else:
        if editing_entry:
            form = form_class(instance=editing_entry, ledger_type=ledger_type)
            form.fields["voucher_number"].widget.attrs["readonly"] = True
        else:
            active_session = Session.objects.filter(status="current_session").order_by("-id").first()
            from .models import _next_expense_voucher
            initial = {"date": dt_date.today()}
            if active_session:
                initial["session"] = active_session.id
            if ledger_type == "Expense":
                initial["voucher_number"] = _next_expense_voucher()
            form = form_class(initial=initial, ledger_type=ledger_type)

        form.fields["voucher_number"].widget.attrs["autofocus"] = True

    # Filters
    month_str = request.GET.get("month", "").strip()
    name_q = request.GET.get("name", "").strip()
    selected_session = request.GET.get("session", "").strip()
    selected_major_head = request.GET.get("major_head", "").strip()
    selected_head = request.GET.get("head", "").strip()
    selected_sub_head = request.GET.get("sub_head", "").strip()

    qs = model.objects.all()
    month_start = None
    month_end = None
    
    if month_str:
        try:
            y, m = month_str.split("-")
            y, m = int(y), int(m)
            last_day = calendar.monthrange(y, m)[1]
            month_start = dt_date(y, m, 1)
            month_end = dt_date(y, m, last_day)
            qs = qs.filter(date__gte=month_start, date__lte=month_end)
        except (ValueError, TypeError):
            month_str = ""

    if name_q:
        from django.db.models import Q
        qs = qs.filter(
            Q(sub_head__icontains=name_q) | Q(employee__name__icontains=name_q)
        )

    if selected_session:
        try:
            qs = qs.filter(session_id=int(selected_session))
        except (ValueError, TypeError):
            pass

    if selected_major_head:
        qs = qs.filter(major_head=selected_major_head)
    
    # Filter by head
    if selected_head:
        qs = qs.filter(head=selected_head)

    # Filter by sub_head
    if selected_sub_head:
        qs = qs.filter(sub_head=selected_sub_head)

    # Optimize queries with select_related for ForeignKeys
    entries = qs.select_related('session').order_by("-date", "-id")
    total_amount = entries.aggregate(total=Sum("amount"))["total"] or 0

    from django.utils import timezone
    today = timezone.localdate()
    if not month_start:
        month_start = today.replace(day=1)
    if not month_end:
        month_end = today
    
    show_add = request.resolver_match.url_name != "expenses_list" if request.resolver_match else True

    return render(
        request,
        template_name,
        {
            "form": form,
            "entries": entries,
            "editing_entry": editing_entry,
            "filter_month": month_str,
            "filter_name": name_q,
            "selected_session": selected_session,
            "selected_major_head": selected_major_head,
            "selected_head": selected_head,
            "selected_sub_head": selected_sub_head,
            "session_choices": Session.objects.all().order_by("session"),
            "major_heads": Head.objects.filter(ledger_type=ledger_type).values_list("major_head", flat=True).distinct().order_by("major_head"),
            "head_data_json": _build_head_data(),
            "filter_head_data_json": _build_filter_head_data(),
            "month_start": month_start,
            "today": month_end,
            "month_total": total_amount,
            "show_add": show_add,
            "page_title": page_title,
            "employees": Employee.objects.exclude(status='left').order_by('name'),
        },
    )


@role_required('accountant', 'admin')
@never_cache
def expenses_home(request):
    """View for expense entries"""
    return _ledger_view(request, Expense, ExpenseForm, "dailyLedger/expense_home.html", "Expenses", ledger_type="Expense")


@role_required('accountant', 'admin')
@never_cache
def income_home(request):
    """View for income entries - handles both regular and fee income"""
    from .forms import IncomeFeesForm
    from django.db.models import Q, Sum
    from students.models import FeesAccount
    
    other_form = None
    fees_form = None
    editing_income_type = None
    income_type = request.POST.get('income_type', 'other')
    incomes = Income.objects.all()
    head_data_json = _build_head_data()
    sessions = Session.objects.all()
    current_session = Session.objects.filter(status='current_session').order_by('-id').first()
    default_session_initial = {'session': current_session.id} if current_session else {}

    # Edit mode
    edit_id = request.GET.get('edit')
    editing_entry = Income.objects.filter(pk=edit_id).first() if edit_id else None
    if editing_entry:
        editing_income_type = 'fees' if editing_entry.fees_account_id else 'other'
    
    # Get filter values from GET request
    selected_session = request.GET.get('session', '').strip()
    if not selected_session and current_session:
        selected_session = str(current_session.id)
    selected_major_head = request.GET.get('major_head', '')
    selected_head = request.GET.get('head', '')
    selected_sub_head = request.GET.get('sub_head', '')
    selected_account = request.GET.get('account_id', '')
    
    # Apply filters
    if selected_session:
        incomes = incomes.filter(session_id=selected_session)
    if selected_major_head:
        incomes = incomes.filter(major_head=selected_major_head)
    if selected_head:
        incomes = incomes.filter(head=selected_head)
    if selected_sub_head:
        incomes = incomes.filter(sub_head=selected_sub_head)
    if selected_account:
        incomes = incomes.filter(fees_account_id=selected_account)
    
    # Get unique values for filter dropdowns
    major_heads = Income.objects.values_list('major_head', flat=True).distinct().order_by('major_head')
    heads = Income.objects.values_list('head', flat=True).distinct().order_by('head')
    sub_heads = Income.objects.values_list('sub_head', flat=True).distinct().order_by('sub_head')
    
    # Get all fee accounts
    fee_accounts = FeesAccount.objects.all().order_by('account_id')
    
    # Calculate total
    income_total = incomes.aggregate(total=Sum('amount'))['total'] or 0
    
    if request.method == "POST":
        entry_id = request.POST.get('entry_id')
        if entry_id:
            # Update existing income entry
            entry = get_object_or_404(Income, pk=entry_id)
            edit_form_type = request.POST.get('income_type') or ('fees' if entry.fees_account_id else 'other')
            if edit_form_type == 'fees':
                fees_form = IncomeFeesForm(request.POST, instance=entry)
                if fees_form.is_valid():
                    fees_form.save()
                    messages.success(request, "Fee income updated successfully!")
                    return redirect("income_home")
                other_form = IncomeForm(ledger_type='Income', initial=default_session_initial)
                editing_income_type = 'fees'
            else:
                other_form = IncomeForm(request.POST, instance=entry, ledger_type='Income')
                if other_form.is_valid():
                    other_form.save()
                    messages.success(request, "Income entry updated successfully!")
                    return redirect("income_home")
                fees_form = IncomeFeesForm(initial=default_session_initial)
                editing_income_type = 'other'
        elif income_type == 'fees':
            fees_form = IncomeFeesForm(request.POST)
            if fees_form.is_valid():
                fees_form.save()
                messages.success(request, "Fee income recorded successfully!")
                return redirect("income_home")
            other_form = IncomeForm(ledger_type='Income', initial=default_session_initial)
        else:
            other_form = IncomeForm(request.POST, ledger_type='Income')
            if other_form.is_valid():
                other_form.save()
                messages.success(request, "Income recorded successfully!")
                return redirect("income_home")
            fees_form = IncomeFeesForm(initial=default_session_initial)
    else:
        if editing_entry:
            if editing_income_type == 'fees':
                fees_form = IncomeFeesForm(instance=editing_entry)
                other_form = IncomeForm(ledger_type='Income', initial=default_session_initial)
            else:
                other_form = IncomeForm(instance=editing_entry, ledger_type='Income')
                fees_form = IncomeFeesForm(initial=default_session_initial)
        else:
            other_form = IncomeForm(ledger_type='Income', initial=default_session_initial)
            fees_form = IncomeFeesForm(initial=default_session_initial)
    
    return render(request, "dailyLedger/income_home.html", {
        "incomes": incomes,
        "other_form": other_form,
        "fees_form": fees_form,
        "head_data_json": head_data_json,
        "sessions": sessions,
        "major_heads": major_heads,
        "heads": heads,
        "sub_heads": sub_heads,
        "fee_accounts": fee_accounts,
        "selected_session": selected_session,
        "selected_major_head": selected_major_head,
        "selected_head": selected_head,
        "selected_sub_head": selected_sub_head,
        "selected_account": selected_account,
        "income_total": income_total,
        "editing_entry": editing_entry,
        "editing_income_type": editing_income_type,
        "current_session": current_session,
    })


@never_cache
def delete_expense(request, pk):
    """Delete an expense entry"""
    obj = get_object_or_404(Expense, pk=pk)
    if request.method == "POST":
        obj.delete()
        return redirect("expenses_home")
    return render(request, "dailyLedger/delete_expense.html", {"entry": obj})


@never_cache
def delete_income(request, pk):
    """Delete an income entry"""
    obj = get_object_or_404(Income, pk=pk)
    if request.method == "POST":
        obj.delete()
        return redirect("income_home")
    return render(request, "dailyLedger/delete_income.html", {"entry": obj})


@role_required('admin')
@never_cache
def heads_home(request):
    edit_id = request.GET.get("edit")
    editing_head = Head.objects.filter(pk=edit_id).first() if edit_id else None

    if request.method == "POST":
        head_id = request.POST.get("head_id")
        if head_id:
            form = HeadForm(request.POST, instance=get_object_or_404(Head, pk=head_id))
        else:
            form = HeadForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("heads_home")
    else:
        form = HeadForm(instance=editing_head) if editing_head else HeadForm()
        form.fields["major_head"].widget.attrs["autofocus"] = True

    selected_major = request.GET.get("major_head", "").strip()
    selected_head = request.GET.get("head", "").strip()
    selected_sub_head = request.GET.get("sub_head", "").strip()
    selected_ledger_type = request.GET.get("ledger_type", "").strip()

    qs = Head.objects.all()
    if selected_major:
        qs = qs.filter(major_head=selected_major)
    if selected_head:
        qs = qs.filter(head=selected_head)
    if selected_sub_head:
        qs = qs.filter(sub_head=selected_sub_head)
    if selected_ledger_type:
        qs = qs.filter(ledger_type=selected_ledger_type)

    major_head_choices = Head.objects.values_list("major_head", flat=True).distinct().order_by("major_head")
    head_choices = Head.objects.values_list("head", flat=True).distinct().order_by("head")

    return render(
        request,
        "dailyLedger/heads_home.html",
        {
            "form": form,
            "heads": qs,
            "editing_head": editing_head,
            "major_head_choices": major_head_choices,
            "head_choices": head_choices,
            "selected_major": selected_major,
            "selected_head": selected_head,
            "selected_sub_head": selected_sub_head,
            "selected_ledger_type": selected_ledger_type,
            "head_data_json": _build_head_data(),
        },
    )


@never_cache
def delete_head(request, pk):
    obj = get_object_or_404(Head, pk=pk)
    if request.method == "POST":
        obj.delete()
        return redirect("heads_home")
    return render(request, "dailyLedger/delete_head.html", {"head_obj": obj})


@never_cache
def sessions_home(request):
    edit_id = request.GET.get("edit")
    editing_session = Session.objects.filter(pk=edit_id).first() if edit_id else None

    if request.method == "POST":
        session_id = request.POST.get("session_id")
        if session_id:
            form = SessionForm(request.POST, instance=get_object_or_404(Session, pk=session_id))
        else:
            form = SessionForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("sessions_home")
    else:
        form = SessionForm(instance=editing_session) if editing_session else SessionForm()
        form.fields["session"].widget.attrs["autofocus"] = True

    selected_session = request.GET.get("session", "").strip()
    qs = Session.objects.all()
    if selected_session:
        qs = qs.filter(session=selected_session)

    sessions = qs.order_by("-id")
    session_choices = Session.objects.values_list("session", flat=True).distinct().order_by("session")

    return render(
        request,
        "dailyLedger/sessions_home.html",
        {
            "form": form,
            "sessions": sessions,
            "editing_session": editing_session,
            "session_choices": session_choices,
            "selected_session": selected_session,
        },
    )


@never_cache
def delete_session(request, pk):
    obj = get_object_or_404(Session, pk=pk)
    if request.method == "POST":
        obj.delete()
        return redirect("sessions_home")
    return render(request, "dailyLedger/delete_session.html", {"session_obj": obj})


@never_cache
def bulk_import(request):
    """Handle bulk import of account heads from CSV"""
    import_result = None
    
    if request.method == "POST":
        form = BulkImportForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data["csv_file"]
            import_type = form.cleaned_data["import_type"]
            handle_duplicates = form.cleaned_data["handle_duplicates"]
            dry_run = form.cleaned_data["dry_run"]
            
            try:
                # Read CSV file
                csv_content = csv_file.read().decode('utf-8')
                
                # Parse and validate CSV
                parse_result = parse_csv_account_heads(csv_content, handle_duplicates)
                
                if parse_result["errors"]:
                    for row_num, error_msg in parse_result["errors"]:
                        messages.error(request, f"Row {row_num}: {error_msg}")
                
                if parse_result["warnings"]:
                    for row_num, warning_msg in parse_result["warnings"]:
                        messages.warning(request, f"Row {row_num}: {warning_msg}")
                
                # Process import if no critical errors
                if parse_result["valid_rows"] or parse_result["duplicate_rows"]:
                    if not dry_run:
                        # Actually import the data
                        import_result = import_account_heads(
                            parse_result["valid_rows"],
                            parse_result["duplicate_rows"],
                            handle_duplicates
                        )
                        
                        # Show success messages
                        if import_result["created"]:
                            messages.success(request, f"Created {import_result['created']} new account head(s)")
                        if import_result["updated"]:
                            messages.success(request, f"Updated {import_result['updated']} account head(s)")
                        if import_result["skipped"]:
                            messages.info(request, f"Skipped {import_result['skipped']} duplicate(s)")
                        if import_result["errors"]:
                            for row_num, error_msg in import_result["errors"]:
                                messages.error(request, f"Row {row_num}: {error_msg}")
                    else:
                        # Dry-run mode: show what would happen
                        import_result = {
                            "created": len(parse_result["valid_rows"]),
                            "updated": len(parse_result["duplicate_rows"]) if handle_duplicates == "update" else 0,
                            "skipped": len(parse_result["duplicate_rows"]) if handle_duplicates == "skip" else 0,
                            "dry_run": True,
                            "valid_rows": parse_result["valid_rows"],
                            "duplicate_rows": parse_result["duplicate_rows"],
                            "handle_duplicates": handle_duplicates
                        }
                        messages.info(request, "Dry-run mode: No data was imported. Review above and uncheck 'Dry Run' to proceed.")
                else:
                    messages.error(request, "No valid data to import")
                    
            except Exception as e:
                messages.error(request, f"Error processing file: {str(e)}")
    else:
        form = BulkImportForm()
    
    return render(
        request,
        "dailyLedger/bulk_import_heads.html",
        {
            "form": form,
            "import_result": import_result,
        }
    )


@never_cache
def download_template(request):
    """Download sample CSV template for bulk import"""
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="account_heads_template.csv"'
    
    writer = csv.writer(response)
    
    # Header row
    writer.writerow(['Ledger_Type', 'Major_Head', 'Head', 'Sub_Head'])
    
    # Sample rows
    writer.writerow(['Expense', 'Admin', 'Salaries', 'Teaching Staff'])
    writer.writerow(['Expense', 'Admin', 'Salaries', 'Non-Teaching Staff'])
    writer.writerow(['Expense', 'Operations', 'Utilities', 'Electricity'])
    writer.writerow(['Income', 'Fee', 'Student Fees', ''])
    
    return response


@never_cache
def bulk_import_ledger(request):
    """Handle bulk import of ledger entries from CSV"""
    import_result = None
    
    # Determine ledger_type from the current URL path
    ledger_type = 'Income' if 'ledger-income' in request.path else 'Expense'
    page_title = f'Bulk Import {ledger_type} Ledger Entries'
    
    if request.method == "POST":
        form = BulkImportLedgerForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data["csv_file"]
            handle_duplicates = form.cleaned_data["handle_duplicates"]
            dry_run = form.cleaned_data["dry_run"]
            
            try:
                # Read CSV file
                csv_content = csv_file.read().decode('utf-8')
                
                # Parse and validate CSV
                parse_result = parse_csv_ledger_entries(csv_content, handle_duplicates, ledger_type)
                
                # Display all errors and warnings
                if parse_result["errors"]:
                    for row_num, error_msg in parse_result["errors"]:
                        messages.error(request, f"Row {row_num}: {error_msg}")
                
                if parse_result["warnings"]:
                    for row_num, warning_msg in parse_result["warnings"]:
                        messages.warning(request, f"Row {row_num}: {warning_msg}")
                
                # Process import - show dry run results even if there are errors
                if parse_result["valid_rows"] or parse_result["duplicate_rows"] or parse_result["errors"] or parse_result["warnings"]:
                    if not dry_run:
                        # Only actually import if there are no errors
                        if parse_result["errors"]:
                            messages.error(request, "Cannot import: Please fix the errors above")
                        else:
                            # Actually import the data
                            import_result = import_ledger_entries(
                                parse_result["valid_rows"],
                                parse_result["duplicate_rows"],
                                handle_duplicates,
                                ledger_type
                            )
                            
                            # Show success messages
                            if import_result["created"]:
                                messages.success(request, f"Created {import_result['created']} new ledger entry/entries")
                            if import_result["updated"]:
                                messages.success(request, f"Updated {import_result['updated']} ledger entry/entries")
                            if import_result["skipped"]:
                                messages.info(request, f"Skipped {import_result['skipped']} duplicate(s)")
                            if import_result["errors"]:
                                for row_num, error_msg in import_result["errors"]:
                                    messages.error(request, f"Row {row_num}: {error_msg}")
                    else:
                        # Dry-run mode: show what would happen
                        import_result = {
                            "created": len(parse_result["valid_rows"]),
                            "updated": len(parse_result["duplicate_rows"]) if handle_duplicates == "update" else 0,
                            "skipped": len(parse_result["duplicate_rows"]) if handle_duplicates == "skip" else 0,
                            "errors_count": len(parse_result["errors"]),
                            "warnings_count": len(parse_result["warnings"]),
                            "dry_run": True,
                            "valid_rows": parse_result["valid_rows"],
                            "duplicate_rows": parse_result["duplicate_rows"],
                            "handle_duplicates": handle_duplicates
                        }
                        messages.info(request, "Dry-run mode: Review results below. Fix any errors and re-upload to import.")
                else:
                    messages.error(request, "CSV file appears to be empty or invalid")
                    
            except Exception as e:
                messages.error(request, f"Error processing file: {str(e)}")
    else:
        form = BulkImportLedgerForm()
    
    return render(
        request,
        "dailyLedger/bulk_import_ledger.html",
        {
            "form": form,
            "import_result": import_result,
            "page_title": page_title,
            "ledger_type": ledger_type,
        }
    )


@never_cache
def download_ledger_template(request):
    """Download sample CSV template for ledger entries bulk import"""
    ledger_type = 'Income' if 'ledger-income' in request.path else 'Expense'
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    filename = 'income_ledger_template.csv' if ledger_type == 'Income' else 'expense_ledger_template.csv'
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    
    # Header row
    writer.writerow(['Voucher_Number', 'Date', 'Amount', 'Major_Head', 'Head', 'Sub_Head', 'Payment_Type', 'Session', 'Details'])
    
    if ledger_type == 'Income':
        # Sample rows - Income entries
        writer.writerow(['I001', '2024-01-15', '15000', 'Fee', 'Tuition Fee', 'Rahul Sharma', 'Cash', '2023-2024', 'Monthly tuition fee'])
        writer.writerow(['I002', '2024-01-20', '5000', 'Fee', 'Transport Fee', 'Priya Singh', 'Bank Transfer', '2023-2024', 'Bus fee Q3'])
        writer.writerow(['I003', '2024-01-25', '2000', 'Donation', 'Building Fund', 'Parent Donation', 'Cash', '2023-2024', 'Building fund donation'])
        writer.writerow(['I004', '2024-01-28', '3000', 'Fee', 'Exam Fee', 'Amit Kumar', 'Cash', '2023-2024', 'Annual exam fee'])
    else:
        # Sample rows - Expense entries
        writer.writerow(['V001', '2024-01-15', '50000', 'Salary', 'Teacher', 'Poonam Gupta', 'Cash', '2023-2024', 'Employee salary'])
        writer.writerow(['V002', '2024-01-20', '5000', 'Operations', 'Books', 'ABC Book Publishers', 'Credit', '2023-2024', 'Books purchase'])
        writer.writerow(['V003', '2024-01-25', '2000', 'Transport', 'Fuel', 'Van Fuel', 'Cash', '2023-2024', 'Transport fuel'])
        writer.writerow(['V004', '2024-01-28', '1500', 'Operations', 'Maintenance', 'Office Maintenance', 'Cash', '2023-2024', 'General maintenance'])
    
    return response


@never_cache
def fees_structure_list(request):
    """View all fees structures and add/edit on same page"""
    from students.models import Class as StudentClass
    editing_fees = None
    form = None

    # Check if editing a fees structure
    edit_id = request.GET.get('edit')
    if edit_id:
        editing_fees = get_object_or_404(FeesStructure, pk=edit_id)

    if request.method == 'POST':
        if edit_id:
            form = FeesStructureForm(request.POST, instance=editing_fees)
        else:
            form = FeesStructureForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, f'Fees structure {"updated" if edit_id else "added"} successfully!')
            return redirect('fees_structure_list')
        else:
            messages.error(request, 'Failed to save fees structure. Please check the errors below.')
    else:
        if edit_id:
            form = FeesStructureForm(instance=editing_fees)
        else:
            form = FeesStructureForm()

    # Filters for saved entries
    filter_session = request.GET.get('filter_session', '')
    filter_class = request.GET.get('filter_class', '')

    fees_structures = FeesStructure.objects.all().order_by('-session', 'class_code')
    if filter_session:
        fees_structures = fees_structures.filter(session__id=filter_session)
    if filter_class:
        fees_structures = fees_structures.filter(class_code__id=filter_class)

    all_sessions = Session.objects.all().order_by('-session')
    all_classes = StudentClass.objects.all().order_by('age')

    # Resolve selected session name for print title
    selected_session_name = ''
    if filter_session:
        try:
            selected_session_name = Session.objects.get(id=filter_session).session
        except Session.DoesNotExist:
            pass
    else:
        # Auto-detect session if all displayed records share the same session
        distinct_sessions = list({fs.session.session for fs in fees_structures})
        if len(distinct_sessions) == 1:
            selected_session_name = distinct_sessions[0]

    fees_structures = list(fees_structures)

    # Compute column totals
    total_fields = [
        'fee_tuition', 'fee_tc', 'fee_admission',
        'book_set', 'book_diary', 'book_other',
        'uniform_shirt', 'uniform_pant', 'uniform_sweater', 'uniform_hoody',
        'uniform_t_shirt', 'uniform_tie', 'uniform_belt', 'uniform_id_card',
    ]
    totals = {f: sum(getattr(fs, f) or 0 for fs in fees_structures) for f in total_fields}

    return render(request, 'dailyLedger/fees_structure_list.html', {
        'fees_structures': fees_structures,
        'form': form,
        'editing_fees': editing_fees,
        'all_sessions': all_sessions,
        'all_classes': all_classes,
        'filter_session': filter_session,
        'filter_class': filter_class,
        'selected_session_name': selected_session_name,
        'totals': totals,
    })


@never_cache
def add_fees_structure(request):
    """Redirect to fees_structure_list for add/edit functionality"""
    return redirect('fees_structure_list')


@never_cache
def edit_fees_structure(request, pk):
    """Redirect to fees_structure_list for add/edit functionality"""
    from django.urls import reverse
    return redirect(f'{reverse("fees_structure_list")}?edit={pk}')


@never_cache
def delete_fees_structure(request, pk):
    """Delete a fees structure"""
    fees_structure = get_object_or_404(FeesStructure, pk=pk)
    if request.method == 'POST':
        fees_structure.delete()
        messages.success(request, 'Fees structure deleted successfully!')
        return redirect('fees_structure_list')
    
    return render(request, 'dailyLedger/delete_fees_structure.html', {'fees_structure': fees_structure})


FEES_STRUCTURE_CSV_COLUMNS = [
    'session', 'class_code',
    'fee_tuition', 'fee_tc', 'fee_admission',
    'book_set', 'book_diary', 'book_other',
    'uniform_shirt', 'uniform_pant', 'uniform_sweater', 'uniform_hoody',
    'uniform_t_shirt', 'uniform_tie', 'uniform_belt', 'uniform_id_card',
]


@never_cache
def bulk_import_fees_structure(request):
    """Bulk import FeesStructure records from a CSV file."""
    from students.models import Class as StudentClass

    preview_rows = []
    errors = []
    success_count = 0
    dry_run = True

    if request.method == 'POST':
        csv_file = request.FILES.get('csv_file')
        dry_run = request.POST.get('dry_run') == 'on'
        handle_duplicates = request.POST.get('handle_duplicates', 'skip')

        if not csv_file:
            messages.error(request, 'Please upload a CSV file.')
            return redirect('bulk_import_fees_structure')

        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Only CSV files are accepted.')
            return redirect('bulk_import_fees_structure')

        try:
            text = csv_file.read().decode('utf-8-sig')
        except UnicodeDecodeError:
            messages.error(request, 'File encoding not supported. Please use UTF-8.')
            return redirect('bulk_import_fees_structure')

        reader = csv.DictReader(StringIO(text))
        # Normalise header names
        reader.fieldnames = [f.strip().lower() for f in (reader.fieldnames or [])]

        required_cols = {'session', 'class_code'}
        missing = required_cols - set(reader.fieldnames)
        if missing:
            messages.error(request, f'CSV is missing required columns: {", ".join(missing)}')
            return redirect('bulk_import_fees_structure')

        decimal_fields = FEES_STRUCTURE_CSV_COLUMNS[2:]  # all after session, class_code

        for row_num, row in enumerate(reader, start=2):
            row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            session_name = row.get('session', '').strip()
            class_code_val = row.get('class_code', '').strip()

            if not session_name or not class_code_val:
                errors.append(f'Row {row_num}: session and class_code are required.')
                continue

            try:
                session_obj = Session.objects.get(session=session_name)
            except Session.DoesNotExist:
                errors.append(f'Row {row_num}: Session "{session_name}" not found.')
                continue

            try:
                class_obj = StudentClass.objects.get(class_code=class_code_val)
            except StudentClass.DoesNotExist:
                errors.append(f'Row {row_num}: Class code "{class_code_val}" not found.')
                continue

            field_values = {}
            parse_error = False
            for field in decimal_fields:
                raw = row.get(field, '0') or '0'
                try:
                    field_values[field] = float(raw)
                except ValueError:
                    errors.append(f'Row {row_num}: Invalid value "{raw}" for field "{field}".')
                    parse_error = True
                    break

            if parse_error:
                continue

            existing = FeesStructure.objects.filter(session=session_obj, class_code=class_obj).first()
            action = 'add'
            if existing:
                if handle_duplicates == 'skip':
                    action = 'skip'
                elif handle_duplicates == 'update':
                    action = 'update'
                else:
                    errors.append(f'Row {row_num}: Duplicate — {session_name} / {class_code_val} already exists.')
                    continue

            preview_rows.append({
                'row_num': row_num,
                'session': session_name,
                'class_code': class_code_val,
                'action': action,
                **field_values,
            })

            if not dry_run and action != 'skip':
                if action == 'update' and existing:
                    for field, val in field_values.items():
                        setattr(existing, field, val)
                    existing.save()
                else:
                    FeesStructure.objects.create(
                        session=session_obj,
                        class_code=class_obj,
                        **field_values,
                    )
                success_count += 1

        if not dry_run:
            if success_count:
                messages.success(request, f'{success_count} fees structure record(s) imported successfully.')
            if errors:
                for e in errors:
                    messages.error(request, e)
            return redirect('fees_structure_list')

    sessions = Session.objects.all().order_by('-session')
    return render(request, 'dailyLedger/bulk_import_fees_structure.html', {
        'preview_rows': preview_rows,
        'errors': errors,
        'dry_run': dry_run,
        'decimal_fields': FEES_STRUCTURE_CSV_COLUMNS[2:],
    })


@never_cache
def download_fees_structure_template(request):
    """Download a blank CSV template for fees structure bulk import."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="fees_structure_template.csv"'
    writer = csv.writer(response)
    writer.writerow(FEES_STRUCTURE_CSV_COLUMNS)
    # Write a sample row
    writer.writerow([
        '2025-26', '1',
        '1200', '200', '500',
        '800', '100', '0',
        '300', '300', '400', '0',
        '150', '100', '80', '50',
    ])
    return response


# API Endpoints for cascading dropdowns in fee income form
@never_cache
def api_get_classes(request, session_id):
    """Get all classes for a given session"""
    from students.models import Student, Class
    from django.http import JsonResponse
    
    try:
        Session.objects.get(id=session_id)
        class_ids = Student.objects.filter(
            session_id=session_id,
            student_class__isnull=False,
        ).values_list('student_class_id', flat=True).distinct()
        classes = Class.objects.filter(id__in=class_ids).order_by('age')
        class_list = [{'id': c.id, 'name': c.class_code} for c in classes]
        return JsonResponse({'classes': class_list})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@never_cache
def api_get_students(request, session_id, class_id):
    """Get all students for a given session and class"""
    from students.models import Student
    from django.http import JsonResponse
    
    try:
        Session.objects.get(id=session_id)
        students = Student.objects.filter(
            session_id=session_id,
            student_class_id=class_id,
        ).values('id', 'first_name', 'last_name').order_by('first_name', 'last_name')

        student_list = [{'id': s['id'], 'name': f"{s['first_name']} {s['last_name']}"} for s in students]
        return JsonResponse({'students': student_list})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@never_cache
def api_get_student_srn(request, student_id):
    """Get SRN for a given student"""
    from students.models import Student
    from django.http import JsonResponse
    
    try:
        student = Student.objects.get(id=student_id)
        return JsonResponse({
            'srn': student.srn,
            'name': student.name,
            'student_id': student.id
        })
    except Student.DoesNotExist:
        return JsonResponse({'error': 'Student not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@never_cache
def api_get_fee_account(request, srn):
    """Get fee account for a given SRN"""
    from students.models import Student, FeesAccount
    from django.http import JsonResponse
    
    try:
        # Get student by SRN
        student = Student.objects.get(srn=srn)
        
        # Get the fee account linked to this student
        if student.fees_account:
            fee_account = student.fees_account
            return JsonResponse({
                'account_id': fee_account.id,
                'account_name': fee_account.name,
                'account_status': fee_account.account_status,
                'account_open': fee_account.account_open.isoformat()
            })
        else:
            return JsonResponse({'error': 'No fee account assigned to this student'}, status=404)
    except Student.DoesNotExist:
        return JsonResponse({'error': 'Student not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@never_cache
def session_ledger_report(request):
    """Session summary report — one row per session showing income and expenses by major head."""
    sessions = Session.objects.all().order_by('session')
    selected_session_id = request.GET.get('session')

    report_data = []
    income_major_heads = []
    expense_major_heads = []
    selected_session = None

    if selected_session_id and selected_session_id != 'all':
        try:
            selected_session = Session.objects.get(id=selected_session_id)
        except Session.DoesNotExist:
            selected_session_id = None

    # Determine which sessions to summarise
    if selected_session_id == 'all' or not selected_session_id:
        sessions_to_show = list(sessions)
    else:
        sessions_to_show = [selected_session]

    # Build major heads from the relevant sessions
    if selected_session_id:
        if selected_session_id == 'all':
            income_qs_all = Income.objects.all()
            expense_qs_all = Expense.objects.all()
        else:
            income_qs_all = Income.objects.filter(session_id=selected_session_id)
            expense_qs_all = Expense.objects.filter(session_id=selected_session_id)

        income_major_heads = list(income_qs_all.values_list('major_head', flat=True).distinct().order_by('major_head'))
        income_major_heads = [h for h in income_major_heads if h]

        expense_major_heads = list(expense_qs_all.values_list('major_head', flat=True).distinct().order_by('major_head'))
        expense_major_heads = [h for h in expense_major_heads if h]

        income_head_totals = {head: 0.0 for head in income_major_heads}
        expense_head_totals = {head: 0.0 for head in expense_major_heads}

        # One summary row per session
        for session in sessions_to_show:
            income_amounts = []
            expense_amounts = []
            row_total_income = 0
            row_total_expense = 0

            for head in income_major_heads:
                amount = float(Income.objects.filter(
                    session=session, major_head=head
                ).aggregate(total=Sum('amount'))['total'] or 0)
                income_amounts.append(amount)
                row_total_income += amount
                income_head_totals[head] += amount

            for head in expense_major_heads:
                amount = float(Expense.objects.filter(
                    session=session, major_head=head
                ).aggregate(total=Sum('amount'))['total'] or 0)
                expense_amounts.append(amount)
                row_total_expense += amount
                expense_head_totals[head] += amount

            if row_total_income == 0 and row_total_expense == 0:
                continue

            row_balance = row_total_income - row_total_expense
            report_data.append({
                'month_display': session.session,
                'income_amounts': income_amounts,
                'expense_amounts': expense_amounts,
                'total_income': row_total_income,
                'total_expense': row_total_expense,
                'balance': row_balance,
            })

        total_income = sum(m['total_income'] for m in report_data)
        total_expense = sum(m['total_expense'] for m in report_data)
        total_balance = total_income - total_expense
        income_head_totals_list = [income_head_totals[head] for head in income_major_heads]
        expense_head_totals_list = [expense_head_totals[head] for head in expense_major_heads]

    else:
        total_income = 0
        total_expense = 0
        total_balance = 0
        income_head_totals_list = []
        expense_head_totals_list = []

    context = {
        'sessions': sessions,
        'selected_session': selected_session,
        'selected_session_id': selected_session_id,
        'income_major_heads': income_major_heads,
        'expense_major_heads': expense_major_heads,
        'report_data': report_data,
        'total_income': total_income if selected_session_id else 0,
        'total_expense': total_expense if selected_session_id else 0,
        'total_balance': total_balance if selected_session_id else 0,
        'income_head_totals_list': income_head_totals_list if selected_session_id else [],
        'expense_head_totals_list': expense_head_totals_list if selected_session_id else [],
    }

    return render(request, 'dailyLedger/session_ledger_report.html', context)


@never_cache
def monthly_ledger_report(request):
    """Monthly ledger report with FY and session filters."""
    selected_session_id = request.GET.get('session')
    selected_fy = request.GET.get('financial_year')
    context = _build_monthly_ledger_report_data(selected_session_id, selected_fy)
    context['print_mode'] = False
    return render(request, 'dailyLedger/monthly_ledger_report.html', context)


@never_cache
def monthly_ledger_report_csv(request):
    """Export monthly ledger report as CSV for selected filters."""
    selected_session_id = request.GET.get('session')
    selected_fy = request.GET.get('financial_year')
    context = _build_monthly_ledger_report_data(selected_session_id, selected_fy)

    response = HttpResponse(content_type='text/csv')
    session_name = context['selected_session'].session if context['selected_session'] else 'all-sessions'
    response['Content-Disposition'] = f'attachment; filename="monthly_ledger_report_{session_name}_{context["selected_fy"]}.csv"'

    writer = csv.writer(response)
    header = ['Month']
    header.extend(context['income_major_heads'])
    header.append('Total Income')
    header.extend(context['expense_major_heads'])
    header.append('Total Expense')
    header.append('Balance')
    writer.writerow(header)

    for row in context['report_rows']:
        csv_row = [row['month']]
        csv_row.extend([f"{amount:.0f}" for amount in row['income_amounts']])
        csv_row.append(f"{row['total_income']:.0f}")
        csv_row.extend([f"{amount:.0f}" for amount in row['expense_amounts']])
        csv_row.append(f"{row['total_expense']:.0f}")
        csv_row.append(f"{row['balance']:.0f}")
        writer.writerow(csv_row)

    totals = context['totals']
    total_row = ['Total']
    total_row.extend([f"{total:.0f}" for total in context['income_head_totals_list']])
    total_row.append(f"{totals['total_income']:.0f}")
    total_row.extend([f"{total:.0f}" for total in context['expense_head_totals_list']])
    total_row.append(f"{totals['total_expense']:.0f}")
    total_row.append(f"{totals['balance']:.0f}")
    writer.writerow(total_row)

    return response


@never_cache
def monthly_ledger_report_pdf(request):
    """Print-friendly monthly report page for Save as PDF from browser."""
    selected_session_id = request.GET.get('session')
    selected_fy = request.GET.get('financial_year')
    context = _build_monthly_ledger_report_data(selected_session_id, selected_fy)
    context['print_mode'] = True
    return render(request, 'dailyLedger/monthly_ledger_report.html', context)


@never_cache
def export_expenses_csv(request):
    """Export all expenses to CSV in bulk import format"""
    expenses = Expense.objects.all()
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="expenses.csv"'
    
    writer = csv.writer(response)
    # Headers must match the bulk import format
    writer.writerow(['Voucher_Number', 'Date', 'Amount', 'Major_Head', 'Head', 'Sub_Head', 'Payment_Type', 'Session', 'Details'])
    
    for expense in expenses:
        writer.writerow([
            expense.voucher_number,
            expense.date.strftime('%Y-%m-%d') if expense.date else '',
            expense.amount,
            expense.major_head,
            expense.head,
            expense.sub_head,
            expense.payment_type,
            expense.session.session if expense.session else '',
            expense.details,
        ])
    
    return response


@never_cache
def delete_all_expenses(request):
    """Delete all expenses with confirmation"""
    if request.method == 'POST':
        count, _ = Expense.objects.all().delete()
        messages.success(request, f'Successfully deleted {count} expense records.')
        return redirect('expenses_home')
    
    # Show confirmation page
    expense_count = Expense.objects.count()
    return render(request, 'dailyLedger/confirm_delete_all.html', {
        'item_type': 'Expenses',
        'item_count': expense_count,
        'delete_url': 'delete_all_expenses'
    })


@never_cache
def export_income_csv(request):
    """Export all income to CSV in bulk import format"""
    incomes = Income.objects.all()
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="income.csv"'
    
    writer = csv.writer(response)
    # Headers must match the bulk import format
    writer.writerow(['Voucher_Number', 'Date', 'Amount', 'Major_Head', 'Head', 'Sub_Head', 'Payment_Type', 'Session', 'Details'])
    
    for income in incomes:
        writer.writerow([
            income.voucher_number or '',
            income.date.strftime('%Y-%m-%d') if income.date else '',
            income.amount,
            income.major_head,
            income.head,
            income.sub_head,
            income.payment_type,
            income.session.session if income.session else '',
            income.details,
        ])
    
    return response


@never_cache
def delete_all_income(request):
    """Delete all income with confirmation"""
    if request.method == 'POST':
        count, _ = Income.objects.all().delete()
        messages.success(request, f'Successfully deleted {count} income records.')
        return redirect('income_home')
    
    # Show confirmation page
    income_count = Income.objects.count()
    return render(request, 'dailyLedger/confirm_delete_all.html', {
        'item_type': 'Income',
        'item_count': income_count,
        'delete_url': 'delete_all_income'
    })


@never_cache
def export_heads_csv(request):
    """Export all heads to CSV in bulk import format"""
    heads = Head.objects.all()
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="heads.csv"'
    
    writer = csv.writer(response)
    # Headers must match the bulk import format
    writer.writerow(['Ledger_Type', 'Major_Head', 'Head', 'Sub_Head', 'Status', 'Details'])
    
    for head in heads:
        writer.writerow([
            head.ledger_type,
            head.major_head,
            head.head,
            head.sub_head,
            head.status,
            head.details,
        ])
    
    return response


@never_cache
def delete_all_heads(request):
    """Delete all heads with confirmation"""
    if request.method == 'POST':
        count, _ = Head.objects.all().delete()
        messages.success(request, f'Successfully deleted {count} head records.')
        return redirect('heads_home')
    
    # Show confirmation page
    heads_count = Head.objects.count()
    return render(request, 'dailyLedger/confirm_delete_all.html', {
        'item_type': 'Heads',
        'item_count': heads_count,
        'delete_url': 'delete_all_heads'
    })
