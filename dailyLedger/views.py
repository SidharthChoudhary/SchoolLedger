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
            return redirect(request.resolver_match.url_name)
    else:
        if editing_entry:
            form = form_class(instance=editing_entry, ledger_type=ledger_type)
            form.fields["voucher_number"].widget.attrs["readonly"] = True
        else:
            active_session = Session.objects.filter(status="current_session").order_by("-id").first()
            form = form_class(initial={"session": active_session.id}, ledger_type=ledger_type) if active_session else form_class(ledger_type=ledger_type)

        form.fields["voucher_number"].widget.attrs["autofocus"] = True

    # Filters
    month_str = request.GET.get("month", "").strip()
    name_q = request.GET.get("name", "").strip()
    selected_session = request.GET.get("session", "").strip()
    selected_major_head = request.GET.get("major_head", "").strip()

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
            Q(sub_head__icontains=name_q)
        )

    if selected_session:
        try:
            qs = qs.filter(session_id=int(selected_session))
        except (ValueError, TypeError):
            pass

    if selected_major_head:
        qs = qs.filter(major_head=selected_major_head)
    
    # Filter by head
    selected_head = request.GET.get("head", "").strip()
    if selected_head:
        qs = qs.filter(head=selected_head)
    
    # Filter by sub_head
    selected_sub_head = request.GET.get("sub_head", "").strip()
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
            "session_choices": Session.objects.all().order_by("session"),
            "major_heads": Head.objects.filter(ledger_type=ledger_type).values_list("major_head", flat=True).distinct().order_by("major_head"),
            "head_data_json": _build_head_data(),
            "month_start": month_start,
            "today": month_end,
            "month_total": total_amount,
            "show_add": show_add,
            "page_title": page_title,
        },
    )


@role_required('accountant', 'admin')
def expenses_home(request):
    """View for expense entries"""
    return _ledger_view(request, Expense, ExpenseForm, "dailyLedger/expense_home.html", "Expenses", ledger_type="Expense")


@role_required('accountant', 'admin')
def income_home(request):
    """View for income entries - handles both regular and fee income"""
    from .forms import IncomeFeesForm
    from django.db.models import Q, Sum
    from students.models import FeesAccount
    
    other_form = None
    fees_form = None
    income_type = request.POST.get('income_type', 'other')
    incomes = Income.objects.all()
    head_data_json = _build_head_data()  # Already returns JSON string, don't double-encode
    sessions = Session.objects.all()
    
    # Get filter values from GET request
    selected_session = request.GET.get('session', '')
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
        if income_type == 'fees':
            fees_form = IncomeFeesForm(request.POST)
            if fees_form.is_valid():
                fees_form.save()
                messages.success(request, "Fee income recorded successfully!")
                return redirect("income_home")
            other_form = IncomeForm(ledger_type='Income')
        else:
            other_form = IncomeForm(request.POST, ledger_type='Income')
            if other_form.is_valid():
                other_form.save()
                messages.success(request, "Income recorded successfully!")
                return redirect("income_home")
            fees_form = IncomeFeesForm()
    else:
        other_form = IncomeForm(ledger_type='Income')
        fees_form = IncomeFeesForm()
    
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
    })


def delete_expense(request, pk):
    """Delete an expense entry"""
    obj = get_object_or_404(Expense, pk=pk)
    if request.method == "POST":
        obj.delete()
        return redirect("expenses_home")
    return render(request, "dailyLedger/delete_expense.html", {"entry": obj})


def delete_income(request, pk):
    """Delete an income entry"""
    obj = get_object_or_404(Income, pk=pk)
    if request.method == "POST":
        obj.delete()
        return redirect("income_home")
    return render(request, "dailyLedger/delete_income.html", {"entry": obj})


@role_required('admin')
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


def delete_head(request, pk):
    obj = get_object_or_404(Head, pk=pk)
    if request.method == "POST":
        obj.delete()
        return redirect("heads_home")
    return render(request, "dailyLedger/delete_head.html", {"head_obj": obj})


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


def delete_session(request, pk):
    obj = get_object_or_404(Session, pk=pk)
    if request.method == "POST":
        obj.delete()
        return redirect("sessions_home")
    return render(request, "dailyLedger/delete_session.html", {"session_obj": obj})


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
        }
    )


def download_ledger_template(request):
    """Download sample CSV template for ledger entries bulk import"""
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="ledger_entries_template.csv"'
    
    writer = csv.writer(response)
    
    # Header row
    writer.writerow(['Voucher_Number', 'Date', 'Amount', 'Major_Head', 'Head', 'Sub_Head', 'Payment_Type', 'Session', 'Details'])
    
    # Sample rows - Expenses with simplified structure
    writer.writerow(['V001', '2024-01-15', '50000', 'Salary', 'Teacher', 'Poonam Gupta', 'Cash', '2023-2024', 'Employee salary'])
    writer.writerow(['V002', '2024-01-20', '5000', 'Operations', 'Books', 'ABC Book Publishers', 'Credit', '2023-2024', 'Books purchase'])
    writer.writerow(['V003', '2024-01-25', '2000', 'Transport', 'Fuel', 'Van Fuel', 'Cash', '2023-2024', 'Transport fuel'])
    writer.writerow(['V004', '2024-01-28', '1500', 'Operations', 'Maintenance', 'Office Maintenance', 'Cash', '2023-2024', 'General maintenance'])
    
    return response


def fees_structure_list(request):
    """View all fees structures and add/edit on same page"""
    editing_fees = None
    form = None
    
    # Check if editing a fees structure
    edit_id = request.GET.get('edit')
    if edit_id:
        editing_fees = get_object_or_404(FeesStructure, pk=edit_id)
    
    if request.method == 'POST':
        if edit_id:
            # Editing existing fees structure
            form = FeesStructureForm(request.POST, instance=editing_fees)
        else:
            # Adding new fees structure
            form = FeesStructureForm(request.POST)
        
        if form.is_valid():
            form.save()
            messages.success(request, f'Fees structure {"updated" if edit_id else "added"} successfully!')
            return redirect('fees_structure_list')
    else:
        if edit_id:
            form = FeesStructureForm(instance=editing_fees)
        else:
            form = FeesStructureForm()
    
    fees_structures = FeesStructure.objects.all().order_by('-session', 'class_code')
    return render(request, 'dailyLedger/fees_structure_list.html', {
        'fees_structures': fees_structures,
        'form': form,
        'editing_fees': editing_fees
    })


def add_fees_structure(request):
    """Redirect to fees_structure_list for add/edit functionality"""
    return redirect('fees_structure_list')


def edit_fees_structure(request, pk):
    """Redirect to fees_structure_list for add/edit functionality"""
    from django.urls import reverse
    return redirect(f'{reverse("fees_structure_list")}?edit={pk}')


def delete_fees_structure(request, pk):
    """Delete a fees structure"""
    fees_structure = get_object_or_404(FeesStructure, pk=pk)
    if request.method == 'POST':
        fees_structure.delete()
        messages.success(request, 'Fees structure deleted successfully!')
        return redirect('fees_structure_list')
    
    return render(request, 'dailyLedger/delete_fees_structure.html', {'fees_structure': fees_structure})


# API Endpoints for cascading dropdowns in fee income form
def api_get_classes(request, session_id):
    """Get all classes for a given session"""
    from students.models import SessionClassStudentMap, Class
    from django.http import JsonResponse
    
    try:
        session = Session.objects.get(id=session_id)
        # Get distinct class IDs from the mapping
        class_ids = SessionClassStudentMap.objects.filter(session=session).values_list('student_class_id', flat=True).distinct()
        # Get the actual Class objects
        classes = Class.objects.filter(id__in=class_ids)
        class_list = [{'id': c.id, 'name': c.class_code} for c in classes]
        return JsonResponse({'classes': class_list})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


def api_get_students(request, session_id, class_id):
    """Get all students for a given session and class"""
    from students.models import SessionClassStudentMap
    from django.http import JsonResponse
    
    try:
        session = Session.objects.get(id=session_id)
        students = SessionClassStudentMap.objects.filter(
            session=session,
            student_class_id=class_id
        ).values_list('student_id', 'student__first_name', 'student__last_name').distinct()
        
        student_list = [{'id': s[0], 'name': f"{s[1]} {s[2]}"} for s in students]
        return JsonResponse({'students': student_list})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


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


def session_ledger_report(request):
    """Generate a ledger report for a selected session showing income and expenses by major head"""
    sessions = Session.objects.all()
    selected_session_id = request.GET.get('session')
    
    report_data = []
    income_major_heads = []
    expense_major_heads = []
    
    if selected_session_id:
        try:
            selected_session = Session.objects.get(id=selected_session_id)
            
            # Get all unique income major heads for this session
            income_major_heads = list(Income.objects.filter(
                session_id=selected_session_id
            ).values_list('major_head', flat=True).distinct().order_by('major_head'))
            income_major_heads = [h for h in income_major_heads if h]  # Remove empty strings
            
            # Get all unique expense major heads for this session
            expense_major_heads = list(Expense.objects.filter(
                session_id=selected_session_id
            ).values_list('major_head', flat=True).distinct().order_by('major_head'))
            expense_major_heads = [h for h in expense_major_heads if h]  # Remove empty strings
            
            # Get all months from both Income and Expense for this session
            income_months = Income.objects.filter(
                session_id=selected_session_id
            ).dates('date', 'month', order='ASC')
            
            expense_months = Expense.objects.filter(
                session_id=selected_session_id
            ).dates('date', 'month', order='ASC')
            
            # Combine and deduplicate months
            all_months = sorted(set(list(income_months) + list(expense_months)))
            
            # Initialize column totals
            income_head_totals = {head: 0.0 for head in income_major_heads}
            expense_head_totals = {head: 0.0 for head in expense_major_heads}
            
            # Build report data for each month
            for month in all_months:
                income_amounts = []
                expense_amounts = []
                month_total_income = 0
                month_total_expense = 0
                
                # Get income amounts by major head for this month
                for head in income_major_heads:
                    amount = float(Income.objects.filter(
                        session_id=selected_session_id,
                        major_head=head,
                        date__year=month.year,
                        date__month=month.month
                    ).aggregate(total=Sum('amount'))['total'] or 0)
                    income_amounts.append(amount)
                    month_total_income += amount
                    income_head_totals[head] += amount
                
                # Get expense amounts by major head for this month
                for head in expense_major_heads:
                    amount = float(Expense.objects.filter(
                        session_id=selected_session_id,
                        major_head=head,
                        date__year=month.year,
                        date__month=month.month
                    ).aggregate(total=Sum('amount'))['total'] or 0)
                    expense_amounts.append(amount)
                    month_total_expense += amount
                    expense_head_totals[head] += amount
                
                month_balance = month_total_income - month_total_expense
                
                report_data.append({
                    'month': month,
                    'month_display': month.strftime('%B'),
                    'income_amounts': income_amounts,
                    'expense_amounts': expense_amounts,
                    'total_income': month_total_income,
                    'total_expense': month_total_expense,
                    'balance': month_balance,
                })
            
            # Calculate totals
            total_income = sum(m['total_income'] for m in report_data)
            total_expense = sum(m['total_expense'] for m in report_data)
            total_balance = total_income - total_expense
            
            # Convert totals to lists in same order as major_heads
            income_head_totals_list = [income_head_totals[head] for head in income_major_heads]
            expense_head_totals_list = [expense_head_totals[head] for head in expense_major_heads]
            
        except Session.DoesNotExist:
            selected_session = None
    else:
        selected_session = None
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
