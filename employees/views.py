from decimal import Decimal
from datetime import datetime
import csv

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.db.models import Sum
from django.utils import timezone
from django.contrib import messages
from accounts.decorators import role_required
from django.views.decorators.cache import never_cache

from .models import Employee, EmployeeRegister, EmployeeAttendance, ManualSalaryData
from .forms import EmployeeForm, EmployeeRegisterForm, EmployeeAttendanceForm, ManualSalaryDataForm
from dailyLedger.models import Session, Expense, Income

@role_required('accountant', 'admin', 'teacher')
@never_cache
def employees_home(request):
    edit_id = request.GET.get("edit")
    editing_employee = None

    if edit_id:
        editing_employee = get_object_or_404(Employee, pk=edit_id)

    if request.method == "POST":
        employee_id = request.POST.get("employee_id")

        if employee_id:
            employee = get_object_or_404(Employee, pk=employee_id)
            form = EmployeeForm(request.POST, request.FILES, instance=employee)
        else:
            form = EmployeeForm(request.POST, request.FILES)

        if form.is_valid():
            form.save()
            return redirect("employees_home")

    else:
        form = EmployeeForm(instance=editing_employee) if editing_employee else EmployeeForm()
        form.fields["name"].widget.attrs["autofocus"] = True

    employees = Employee.objects.all()  # ordered by Meta ordering

    return render(
        request,
        "employees/employees_home.html",
        {"form": form, "employees": employees, "editing_employee": editing_employee},
    )


def delete_employee(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if request.method == "POST":
        employee.delete()
        return redirect("employees_home")
    return render(request, "employees/delete_employee.html", {"employee": employee})


def bulk_import_employees(request):
    """Handle bulk import of employees from CSV"""
    from .forms import BulkImportEmployeeForm
    from .utils import parse_csv_employees, import_employees
    
    import_result = None
    
    if request.method == "POST":
        form = BulkImportEmployeeForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data["csv_file"]
            handle_duplicates = form.cleaned_data["handle_duplicates"]
            dry_run = form.cleaned_data["dry_run"]
            
            try:
                # Read CSV file
                csv_content = csv_file.read().decode('utf-8')
                
                # Parse and validate CSV
                parse_result = parse_csv_employees(csv_content, handle_duplicates)
                
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
                        import_result = import_employees(
                            parse_result["valid_rows"],
                            parse_result["duplicate_rows"],
                            handle_duplicates
                        )
                        
                        # Show success messages
                        if import_result["created"]:
                            messages.success(request, f"Created {import_result['created']} new employee/employees")
                        if import_result["updated"]:
                            messages.success(request, f"Updated {import_result['updated']} employee/employees")
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
        form = BulkImportEmployeeForm()
    
    return render(
        request,
        "employees/bulk_import_employees.html",
        {
            "form": form,
            "import_result": import_result,
        }
    )


def download_employees_template(request):
    """Download sample CSV template for employees bulk import"""
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="employees_template.csv"'
    
    writer = csv.writer(response)
    
    # Header row
    writer.writerow(['Name', 'DOB', 'Contact_Number', 'Gender', 'Qualification', 'Address', 'Experience_Years', 'Previous_Institute', 'Post', 'Role', 'Role_Detail', 'Joining_Date', 'Base_Salary_Per_Month', 'Status', 'Leaves_Entitled'])
    
    # Sample rows
    writer.writerow(['John Smith', '1990-05-20', '9876543210', 'M', 'B.Ed', '123 Main Street', '5', 'XYZ School', 'Teacher', 'Class Teacher', 'Class 5A', '2022-01-15', '50000', 'active', '30'])
    writer.writerow(['Jane Doe', '1988-03-15', '9876543211', 'F', 'M.Sc', '456 Oak Avenue', '8.5', 'ABC Institute', 'Senior Teacher', 'Subject Head', 'Mathematics Department', '2020-06-01', '65000', 'active', '25'])
    writer.writerow(['Robert Johnson', '1992-07-10', '9876543212', 'M', 'B.Com', '789 Pine Road', '3', 'MNO College', 'Accountant', 'Staff', 'Finance Department', '2023-04-20', '40000', 'active', '30'])
    
    return response


def bulk_import_manual_salary_data(request):
    """Handle bulk import of manual salary data from CSV"""
    from .forms import BulkImportManualSalaryDataForm
    from .utils import parse_csv_manual_salary_data, import_manual_salary_data
    
    import_result = None
    
    if request.method == "POST":
        form = BulkImportManualSalaryDataForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data["csv_file"]
            handle_duplicates = form.cleaned_data["handle_duplicates"]
            dry_run = form.cleaned_data["dry_run"]
            
            try:
                # Read CSV file
                csv_content = csv_file.read().decode('utf-8')
                
                # Parse and validate CSV
                parse_result = parse_csv_manual_salary_data(csv_content, handle_duplicates)
                
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
                        import_result = import_manual_salary_data(
                            parse_result["valid_rows"],
                            parse_result["duplicate_rows"],
                            handle_duplicates
                        )
                        
                        # Show success messages
                        if import_result["created"]:
                            messages.success(request, f"Created {import_result['created']} new entry/entries")
                        if import_result["updated"]:
                            messages.success(request, f"Updated {import_result['updated']} entry/entries")
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
        form = BulkImportManualSalaryDataForm()
    
    return render(
        request,
        "employees/bulk_import_manual_salary_data.html",
        {
            "form": form,
            "import_result": import_result,
        }
    )


def download_manual_salary_data_template(request):
    """Download sample CSV template for manual salary data bulk import"""
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="manual_salary_data_template.csv"'
    
    writer = csv.writer(response)
    
    # Header row
    writer.writerow(['Session', 'Employee_Name', 'Amount_Type', 'Amount', 'Month', 'Note'])
    
    # Sample rows
    writer.writerow(['2024', 'John Smith', 'salary', '50000', '2024-01', 'January salary adjustment'])
    writer.writerow(['2024', 'Jane Doe', 'old_due', '15000', '2024-01', 'Previous month arrears'])
    writer.writerow(['2024', 'Robert Johnson', 'salary', '45000', '2024-02', 'February salary'])
    
    return response


def employee_register(request):
    """Employee Register page for tracking attendance and paid days"""
    edit_id = request.GET.get("edit")
    editing_register = None

    if edit_id:
        editing_register = get_object_or_404(EmployeeRegister, pk=edit_id)

    if request.method == "POST":
        register_id = request.POST.get("register_id")

        if register_id:
            register = get_object_or_404(EmployeeRegister, pk=register_id)
            form = EmployeeRegisterForm(request.POST, instance=register)
        else:
            form = EmployeeRegisterForm(request.POST)

        if form.is_valid():
            form.save()
            return redirect("employee_register")

    else:
        form = EmployeeRegisterForm(instance=editing_register) if editing_register else EmployeeRegisterForm()

    # Filters
    selected_session = request.GET.get("session")
    
    registers = EmployeeRegister.objects.select_related("employee", "session").all()
    
    if selected_session:
        registers = registers.filter(session_id=selected_session)
    else:
        # Default to Current Session
        active_session = Session.objects.filter(status="current_session").first()
        if active_session:
            registers = registers.filter(session=active_session)
            selected_session = str(active_session.id)

    session_choices = Session.objects.all()

    return render(
        request,
        "employees/employee_register.html",
        {
            "form": form,
            "registers": registers,
            "editing_register": editing_register,
            "session_choices": session_choices,
            "selected_session": selected_session,
        },
    )


def delete_register(request, pk):
    """Delete an employee register entry"""
    register = get_object_or_404(EmployeeRegister, pk=pk)
    if request.method == "POST":
        register.delete()
        return redirect("employee_register")
    return render(request, "employees/delete_register.html", {"register": register})


def manual_salary_data(request):
    """Manage manual salary data (old dues and adjustments)"""
    edit_id = request.GET.get("edit")
    editing_record = ManualSalaryData.objects.filter(pk=edit_id).first() if edit_id else None

    if request.method == "POST":
        record_id = request.POST.get("record_id")
        if record_id:
            form = ManualSalaryDataForm(request.POST, instance=get_object_or_404(ManualSalaryData, pk=record_id))
        else:
            form = ManualSalaryDataForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("manual_salary_data")
    else:
        form = ManualSalaryDataForm(instance=editing_record) if editing_record else ManualSalaryDataForm()
        if not editing_record:
            form.fields["employee"].widget.attrs["autofocus"] = True

    # Filter records by employee name, month, and session
    selected_employee = request.GET.get("employee", "").strip()
    selected_month = request.GET.get("month", "").strip()
    selected_session = request.GET.get("session", "").strip()
    
    records = ManualSalaryData.objects.select_related('session', 'employee').all()
    
    if selected_employee:
        records = records.filter(employee__name__icontains=selected_employee)
    
    if selected_month:
        records = records.filter(month=selected_month)
    
    if selected_session:
        records = records.filter(session__session=selected_session)
    
    records = records.order_by('-id')
    
    # Calculate total amount
    total_amount = sum(record.amount for record in records)
    
    # Get list of employee names for filter dropdown
    employee_list = Employee.objects.filter(status='active').values_list('name', flat=True).distinct().order_by('name')
    
    # Get list of months from ManualSalaryData
    month_list = ManualSalaryData.objects.values_list('month', flat=True).distinct().order_by('-month')
    
    # Get list of sessions from ManualSalaryData
    session_list = ManualSalaryData.objects.select_related('session').values_list('session__session', flat=True).distinct().order_by('-session__session')

    return render(
        request,
        "employees/manual_salary_data.html",
        {
            "form": form,
            "records": records,
            "editing_record": editing_record,
            "selected_employee": selected_employee,
            "selected_month": selected_month,
            "selected_session": selected_session,
            "employee_list": employee_list,
            "month_list": month_list,
            "session_list": session_list,
            "total_amount": total_amount,
        },
    )


def delete_manual_salary_data(request, pk):
    """Delete a manual salary data entry"""
    record = get_object_or_404(ManualSalaryData, pk=pk)
    if request.method == "POST":
        record.delete()
        return redirect("manual_salary_data")
    return render(request, "employees/delete_manual_salary_data.html", {"record": record})


def employees_view(request):
    employees = Employee.objects.all()

    # --- filters ---
    selected_post = request.GET.get("post")
    selected_status = request.GET.get("status")

    if selected_post:
        employees = employees.filter(post__iexact=selected_post)

    if selected_status:
        employees = employees.filter(status=selected_status)

    # --- total salary (filtered) ---
    total_salary = employees.aggregate(
        total=Sum("base_salary_per_month")
    )["total"] or 0

    # dropdown values
    post_choices = (
        Employee.objects.values_list("post", flat=True)
        .exclude(post="")
        .distinct()
    )

    status_choices = Employee.STATUS_CHOICES

    return render(
        request,
        "employees/employees_view.html",
        {
            "employees": employees,
            "total_salary": total_salary,
            "post_choices": post_choices,
            "status_choices": status_choices,
            "selected_post": selected_post,
            "selected_status": selected_status,
        },
    )


def new_employee_statements(request):
    """Employee Statement parameters page (no statement type)"""
    if request.method == "POST":
        employee_id = request.POST.get("employee")
        session_id = request.POST.get("session")
        # month may be present but employees_statement does not require it
        if not employee_id:
            return redirect("select_statement_type")
        # Redirect to single-employee comprehensive statement
        return redirect(f"/employees/statement/?employee={employee_id}&session={session_id}")
    
    employees = Employee.objects.all().order_by("name")
    sessions = Session.objects.all().order_by("-session")
    
    # Get unique months from EmployeeRegister
    months = EmployeeRegister.objects.values_list("month", flat=True).distinct().order_by("-month")
    month_choices = []
    for m in months:
        try:
            month_label = datetime.strptime(m, "%Y-%m").strftime("%B %Y")
            month_choices.append({"value": m, "label": month_label})
        except (ValueError, TypeError):
            month_choices.append({"value": m, "label": m})
    
    context = {
        "employees": employees,
        "sessions": sessions,
        "month_choices": month_choices,
    }
    
    return render(request, "employees/new_employee_statements.html", context)


def select_statement_type(request):
    """First step: choose Employee vs Employees statements"""
    return render(request, "employees/select_statement_type.html", {})


def select_employee_salary_statement_params(request):
    """Parameters page for Employee Salary Statement"""
    if request.method == "POST":
        employee_id = request.POST.get("employee")
        return redirect(f"/employees/salary-statement/{employee_id}/")
    
    employees = Employee.objects.all().order_by("name")
    
    return render(
        request,
        "employees/select_employee_salary_statement_params.html",
        {"employees": employees}
    )


def select_employee_salary_payment_details_params(request):
    """Parameters page for Employee Salary-Payment Details"""
    if request.method == "POST":
        employee_id = request.POST.get("employee")
        return redirect(f"/employees/salary-payment-details/{employee_id}/")
    
    employees = Employee.objects.all().order_by("name")
    
    return render(
        request,
        "employees/select_employee_salary_payment_details_params.html",
        {"employees": employees}
    )


def select_employee_monthly_params(request):
    """Parameters page for Employee Monthly Statement"""
    if request.method == "POST":
        employee_id = request.POST.get("employee")
        session_id = request.POST.get("session")
        month = request.POST.get("month")
        return redirect(f"/employees/employee-monthly/?employee={employee_id}&session={session_id}&month={month}")

    employees = Employee.objects.all().order_by("name")
    sessions = Session.objects.all().order_by("-session")
    months = EmployeeRegister.objects.values_list("month", flat=True).distinct().order_by("-month")
    month_choices = []
    for m in months:
        try:
            month_label = datetime.strptime(m, "%Y-%m").strftime("%B %Y")
            month_choices.append({"value": m, "label": month_label})
        except (ValueError, TypeError):
            month_choices.append({"value": m, "label": m})
    return render(request, "employees/select_employee_monthly_params.html", {"employees": employees, "sessions": sessions, "month_choices": month_choices})


def select_employee_yearly_params(request):
    """Parameters page for Employee Yearly Statement"""
    if request.method == "POST":
        employee_id = request.POST.get("employee")
        session_id = request.POST.get("session")
        year = request.POST.get("year")
        # pass a month value using the selected year (January)
        month = f"{year}-01" if year else ""
        return redirect(f"/employees/employee-yearly/?employee={employee_id}&session={session_id}&month={month}")

    employees = Employee.objects.all().order_by("name")
    sessions = Session.objects.all().order_by("-session")
    # Build year choices from EmployeeRegister months
    months = EmployeeRegister.objects.values_list("month", flat=True).distinct()
    years = sorted({m.split("-")[0] for m in months if m}, reverse=True)
    year_choices = [{"value": y, "label": y} for y in years]
    return render(request, "employees/select_employee_yearly_params.html", {"employees": employees, "sessions": sessions, "year_choices": year_choices})


def select_employees_monthly_params(request):
    """Parameters page for Employees Monthly Statement"""
    if request.method == "POST":
        session_id = request.POST.get("session")
        month = request.POST.get("month")
        return redirect(f"/employees/employees-monthly/?session={session_id}&month={month}")

    sessions = Session.objects.all().order_by("-session")
    months = EmployeeRegister.objects.values_list("month", flat=True).distinct().order_by("-month")
    month_choices = []
    for m in months:
        try:
            month_label = datetime.strptime(m, "%Y-%m").strftime("%B %Y")
            month_choices.append({"value": m, "label": month_label})
        except (ValueError, TypeError):
            month_choices.append({"value": m, "label": m})
    return render(request, "employees/select_employees_monthly_params.html", {"sessions": sessions, "month_choices": month_choices})


def select_employees_yearly_params(request):
    """Parameters page for Employees Yearly Statement"""
    if request.method == "POST":
        session_id = request.POST.get("session")
        return redirect(f"/employees/employees-yearly/?session={session_id}")

    sessions = Session.objects.all().order_by("-session")
    return render(request, "employees/select_employees_yearly_params.html", {"sessions": sessions})


def select_pay_slip_params(request):
    """Parameters page for Pay Slip"""
    if request.method == "POST":
        employee_id = request.POST.get("employee")
        session_id = request.POST.get("session")
        month = request.POST.get("month")
        return redirect(f"/employees/pay-slip/?employee={employee_id}&session={session_id}&month={month}")

    employees = Employee.objects.all().order_by("name")
    sessions = Session.objects.all().order_by("-session")
    months = EmployeeRegister.objects.values_list("month", flat=True).distinct().order_by("-month")
    month_choices = []
    for m in months:
        try:
            month_label = datetime.strptime(m, "%Y-%m").strftime("%B %Y")
            month_choices.append({"value": m, "label": month_label})
        except (ValueError, TypeError):
            month_choices.append({"value": m, "label": m})
    return render(request, "employees/select_pay_slip_params.html", {"employees": employees, "sessions": sessions, "month_choices": month_choices})


def employees_summary_statement(request):
    """Employees Summary Statement - big table across all months (optional session filter)"""
    session_id = request.GET.get("session")
    session = get_object_or_404(Session, pk=session_id) if session_id else None

    employees = Employee.objects.all().order_by("name")
    zero = Decimal("0")
    rows = []
    grand_payable = zero
    grand_paid = zero

    for emp in employees:
        reg_qs = EmployeeRegister.objects.filter(employee=emp)
        if session_id:
            reg_qs = reg_qs.filter(session_id=session_id)
        # Sum payable across all months
        total_payable = reg_qs.aggregate(total=Sum("payable_salary"))["total"] or zero

        paid_qs = Expense.objects.filter(
            account_type='employee',
            employee_id=emp.id,
        )
        if session_id:
            paid_qs = paid_qs.filter(session_id=session_id)
        total_paid = paid_qs.aggregate(total=Sum("amount"))["total"] or zero

        total_due = (total_payable or zero) - (total_paid or zero)

        rows.append({
            "employee_name": emp.name,
            "employee_id": emp.emp_no,
            "base_salary": emp.base_salary_per_month,
            "total_payable": total_payable,
            "total_paid": total_paid,
            "total_due": total_due,
        })

        grand_payable += total_payable
        grand_paid += total_paid

    grand_due = grand_payable - grand_paid

    context = {
        "session": session,
        "rows": rows,
        "grand_payable": grand_payable,
        "grand_paid": grand_paid,
        "grand_due": grand_due,
        "statement_date": timezone.localdate(),
    }

    return render(request, "employees/employees_summary_statement.html", context)


def salary_statement_view(request):
    """Generate salary statement for specific employee, session, and month"""
    employee_id = request.GET.get("employee")
    session_id = request.GET.get("session")
    month = request.GET.get("month")
    
    employee = get_object_or_404(Employee, pk=employee_id) if employee_id else None
    session = get_object_or_404(Session, pk=session_id) if session_id else None
    
    if not employee:
        return redirect("new_employee_statements")
    
    # Get month display
    try:
        month_display = datetime.strptime(month, "%Y-%m").strftime("%B %Y") if month else "All Months"
    except (ValueError, TypeError):
        month_display = month or "All Months"
    
    # Filter register entries - show all months, optionally filtered by session
    registers = EmployeeRegister.objects.filter(employee=employee).select_related("session", "employee")
    
    if session_id:
        registers = registers.filter(session_id=session_id)
    # Don't filter by month - show all months
    
    registers = registers.order_by("-session__session", "-month")
    
    monthly_rows = []
    session_summary = {}
    zero = Decimal("0")
    total_payable = zero
    total_paid = zero
    
    for reg in registers:
        try:
            year, m = reg.month.split("-")
            year = int(year)
            m = int(m)
        except (ValueError, AttributeError):
            year = None
            m = None
        
        paid_qs = Expense.objects.filter(
            account_type='employee',
            employee_id=employee.id,
        )
        
        if reg.session_id:
            paid_qs = paid_qs.filter(session_id=reg.session_id)
        
        if year and m:
            paid_qs = paid_qs.filter(date__year=year, date__month=m)
        
        paid_amount = paid_qs.aggregate(total=Sum("amount"))["total"] or zero
        
        payable_salary = reg.payable_salary or zero
        due_salary = payable_salary - paid_amount
        
        monthly_rows.append(
            {
                "session": reg.session.session if reg.session else "—",
                "month_label": reg.month_display,
                "base_salary": employee.base_salary_per_month,
                "payable_salary": payable_salary,
                "paid_salary": paid_amount,
                "due_salary": due_salary,
            }
        )
        
        session_key = reg.session.session if reg.session else "—"
        if session_key not in session_summary:
            session_summary[session_key] = {"payable": zero, "paid": zero, "due": zero}
        session_summary[session_key]["payable"] += payable_salary
        session_summary[session_key]["paid"] += paid_amount
        session_summary[session_key]["due"] = session_summary[session_key]["payable"] - session_summary[session_key]["paid"]
        
        total_payable += payable_salary
        total_paid += paid_amount
    
    total_due = total_payable - total_paid
    
    context = {
        "employee": employee,
        "session": session,
        "month_display": month_display,
        "monthly_rows": monthly_rows,
        "session_summary": session_summary,
        "total_payable": total_payable,
        "total_paid": total_paid,
        "total_due": total_due,
        "statement_date": timezone.localdate(),
    }
    
    return render(request, "employees/salary_statement.html", context)


def pay_slip_view(request):
    """Generate pay slip for specific employee, session, and month"""
    employee_id = request.GET.get("employee")
    session_id = request.GET.get("session")
    month = request.GET.get("month")
    
    employee = get_object_or_404(Employee, pk=employee_id) if employee_id else None
    session = get_object_or_404(Session, pk=session_id) if session_id else None
    
    if not employee or not month:
        return redirect("new_employee_statements")
    
    # Get month display
    try:
        month_display = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
    except (ValueError, TypeError):
        month_display = month
    
    # Get register entry
    register = EmployeeRegister.objects.filter(
        employee=employee,
        month=month
    )
    
    if session_id:
        register = register.filter(session_id=session_id)
    
    register = register.first()
    
    if not register:
        context = {
            "employee": employee,
            "session": session,
            "month_display": month_display,
            "error": "No register entry found for the selected parameters.",
        }
        return render(request, "employees/pay_slip.html", context)
    
    # Calculate paid amount from ledger
    try:
        year, m = month.split("-")
        year = int(year)
        m = int(m)
    except (ValueError, AttributeError):
        year = None
        m = None
    
    paid_qs = Expense.objects.filter(
        account_type='employee',
        employee_id=employee.id,
    )
    
    if session_id:
        paid_qs = paid_qs.filter(session_id=session_id)
    
    if year and m:
        paid_qs = paid_qs.filter(date__year=year, date__month=m)
    
    paid_amount = paid_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    zero = Decimal("0")
    payable_salary = register.payable_salary or zero
    paid_days = register.paid_days or zero
    leaves_taken = Decimal("30") - paid_days
    due_salary = payable_salary - paid_amount
    
    context = {
        "employee": employee,
        "session": session,
        "month_display": month_display,
        "register": register,
        "paid_amount": paid_amount,
        "due_salary": due_salary,
        "leaves_taken": leaves_taken,
        "statement_date": timezone.localdate(),
    }
    
    return render(request, "employees/pay_slip.html", context)


def employee_monthly_statement(request):
    """Employee Monthly Statement - 1 employee, 1 month"""
    employee_id = request.GET.get("employee")
    session_id = request.GET.get("session")
    month = request.GET.get("month")
    
    employee = get_object_or_404(Employee, pk=employee_id) if employee_id else None
    session = get_object_or_404(Session, pk=session_id) if session_id else None
    
    if not employee or not month:
        return redirect("new_employee_statements")
    
    try:
        month_display = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
        year, m = month.split("-")
        year = int(year)
        m = int(m)
    except (ValueError, TypeError):
        month_display = month
        year = None
        m = None
    
    # Get register entry for this employee and month
    register = EmployeeRegister.objects.filter(employee=employee, month=month)
    if session_id:
        register = register.filter(session_id=session_id)
    register = register.first()
    
    # Calculate paid amount from ledger
    paid_amount = Decimal("0")
    if register:
        paid_qs = Expense.objects.filter(
            account_type='employee',
            employee_id=employee.id,
        )
        if session_id:
            paid_qs = paid_qs.filter(session_id=session_id)
        if year and m:
            paid_qs = paid_qs.filter(date__year=year, date__month=m)
        paid_amount = paid_qs.aggregate(total=Sum("amount"))["total"] or Decimal("0")
    
    payable_salary = register.payable_salary if register else Decimal("0")
    due_salary = payable_salary - paid_amount
    
    context = {
        "employee": employee,
        "session": session,
        "month_display": month_display,
        "register": register,
        "paid_amount": paid_amount,
        "payable_salary": payable_salary,
        "due_salary": due_salary,
        "statement_date": timezone.localdate(),
    }
    
    return render(request, "employees/employee_monthly_statement.html", context)


def employee_yearly_statement(request):
    """Employee Yearly Statement - 1 employee, all months in 1 year"""
    employee_id = request.GET.get("employee")
    session_id = request.GET.get("session")
    month = request.GET.get("month")
    
    employee = get_object_or_404(Employee, pk=employee_id) if employee_id else None
    session = get_object_or_404(Session, pk=session_id) if session_id else None
    
    if not employee or not month:
        return redirect("new_employee_statements")
    
    try:
        year = month.split("-")[0]
        year_display = year
    except (ValueError, AttributeError):
        year_display = "Unknown"
        year = None
    
    # Get all register entries for this employee in the selected year
    registers = EmployeeRegister.objects.filter(employee=employee)
    if session_id:
        registers = registers.filter(session_id=session_id)
    if year:
        registers = registers.filter(month__startswith=year)
    registers = registers.order_by("month")
    
    monthly_rows = []
    zero = Decimal("0")
    total_payable = zero
    total_paid = zero
    
    for reg in registers:
        try:
            y, m = reg.month.split("-")
            y = int(y)
            m = int(m)
        except (ValueError, AttributeError):
            y = None
            m = None
        
        paid_qs = Expense.objects.filter(
            account_type='employee',
            employee_id=employee.id,
        )
        if reg.session_id:
            paid_qs = paid_qs.filter(session_id=reg.session_id)
        if y and m:
            paid_qs = paid_qs.filter(date__year=y, date__month=m)
        
        paid_amount = paid_qs.aggregate(total=Sum("amount"))["total"] or zero
        payable_salary = reg.payable_salary or zero
        due_salary = payable_salary - paid_amount
        
        monthly_rows.append({
            "month_label": reg.month_display,
            "payable_salary": payable_salary,
            "paid_salary": paid_amount,
            "due_salary": due_salary,
        })
        
        total_payable += payable_salary
        total_paid += paid_amount
    
    total_due = total_payable - total_paid
    
    context = {
        "employee": employee,
        "session": session,
        "year_display": year_display,
        "monthly_rows": monthly_rows,
        "total_payable": total_payable,
        "total_paid": total_paid,
        "total_due": total_due,
        "statement_date": timezone.localdate(),
    }
    
    return render(request, "employees/employee_yearly_statement.html", context)


def employees_monthly_statement(request):
    """Employees Monthly Statement - all employees, 1 month"""
    session_id = request.GET.get("session")
    month = request.GET.get("month")
    
    session = get_object_or_404(Session, pk=session_id) if session_id else None
    
    if not month:
        return redirect("new_employee_statements")
    
    try:
        month_display = datetime.strptime(month, "%Y-%m").strftime("%B %Y")
        year, m = month.split("-")
        year = int(year)
        m = int(m)
    except (ValueError, TypeError):
        month_display = month
        year = None
        m = None
    
    # Include ALL employees regardless of register entries
    employees = Employee.objects.all().order_by("name")
    employee_rows = []
    zero = Decimal("0")
    total_payable = zero
    total_paid = zero

    for emp in employees:
        # Find register for this employee & month (optional session)
        reg_qs = EmployeeRegister.objects.filter(employee=emp, month=month)
        if session_id:
            reg_qs = reg_qs.filter(session_id=session_id)
        reg = reg_qs.select_related("session", "employee").first()

        # Paid from ledger
        paid_qs = Expense.objects.filter(
            account_type='employee',
            employee_id=emp.id,
        )
        if session_id:
            paid_qs = paid_qs.filter(session_id=session_id)
        if year and m:
            paid_qs = paid_qs.filter(date__year=year, date__month=m)

        paid_amount = paid_qs.aggregate(total=Sum("amount"))["total"] or zero
        payable_salary = (reg.payable_salary if reg and reg.payable_salary is not None else zero)
        due_salary = payable_salary - paid_amount

        employee_rows.append({
            "employee_name": emp.name,
            "employee_id": emp.emp_no,
            "payable_salary": payable_salary,
            "paid_salary": paid_amount,
            "due_salary": due_salary,
        })

        total_payable += payable_salary
        total_paid += paid_amount
    
    total_due = total_payable - total_paid
    
    context = {
        "session": session,
        "month_display": month_display,
        "employee_rows": employee_rows,
        "total_payable": total_payable,
        "total_paid": total_paid,
        "total_due": total_due,
        "statement_date": timezone.localdate(),
    }
    
    return render(request, "employees/employees_monthly_statement.html", context)


def employees_yearly_statement(request):
    """Employees Yearly Statement - all employees aggregated over selected session only"""
    session_id = request.GET.get("session")
    session = get_object_or_404(Session, pk=session_id) if session_id else None

    if not session_id:
        return redirect("select_employees_yearly_params")

    employees = Employee.objects.all().order_by("name")
    zero = Decimal("0")
    rows = []
    total_payable = zero
    total_paid = zero

    for emp in employees:
        # Sum payable across all months in the selected session
        reg_qs = EmployeeRegister.objects.filter(employee=emp, session_id=session_id)
        emp_payable = reg_qs.aggregate(total=Sum("payable_salary"))["total"] or zero

        # Sum paid across all expenses for this session
        paid_qs = Expense.objects.filter(
            account_type='employee',
            employee_id=emp.id,
            session_id=session_id,
        )
        emp_paid = paid_qs.aggregate(total=Sum("amount"))["total"] or zero

        emp_due = emp_payable - emp_paid

        rows.append({
            "employee_name": emp.name,
            "payable_salary": emp_payable,
            "paid_salary": emp_paid,
            "due_salary": emp_due,
        })

        total_payable += emp_payable
        total_paid += emp_paid

    total_due = total_payable - total_paid

    context = {
        "session": session,
        "rows": rows,
        "total_payable": total_payable,
        "total_paid": total_paid,
        "total_due": total_due,
        "statement_date": timezone.localdate(),
    }

    return render(request, "employees/employees_yearly_statement.html", context)


def select_ledger_statement_params(request):
    """Parameters page for Ledger Statement"""
    if request.method == "POST":
        session_id = request.POST.get("session")
        return redirect(f"/employees/ledger-statement/?session={session_id}")

    sessions = Session.objects.all().order_by("-session")
    return render(request, "employees/select_ledger_statement_params.html", {"sessions": sessions})


def ledger_statement(request):
    """Ledger Statement - income and expense by session and month"""
    session_id = request.GET.get("session")
    session = get_object_or_404(Session, pk=session_id) if session_id else None

    if not session_id:
        return redirect("select_ledger_statement_params")

    # Group by month
    month_data = {}
    zero = Decimal("0")

    # Fetch all transactions (income and expense)
    all_transactions = Expense.objects.filter(session_id=session_id).order_by("-date")

    for transaction in all_transactions:
        month_key = transaction.date.strftime("%Y-%m")
        try:
            month_label = datetime.strptime(month_key, "%Y-%m").strftime("%B %Y")
        except (ValueError, TypeError):
            month_label = month_key

        if month_key not in month_data:
            month_data[month_key] = {
                "month_label": month_label,
                "income": zero,
                "expense": zero,
            }

        if transaction.ledger_type == "Income":
            month_data[month_key]["income"] += transaction.amount
        elif transaction.ledger_type == "Expense":
            month_data[month_key]["expense"] += transaction.amount

    # Sort by month ascending (Jan → Dec)
    sorted_months = sorted(month_data.items(), key=lambda x: x[0])
    rows = []
    total_income = zero
    total_expense = zero

    for month_key, data in sorted_months:
        balance = data["income"] - data["expense"]
        rows.append({
            "session": session.session,
            "month_label": data["month_label"],
            "income": data["income"],
            "expense": data["expense"],
            "balance": balance,
        })
        total_income += data["income"]
        total_expense += data["expense"]

    total_balance = total_income - total_expense

    context = {
        "session": session,
        "rows": rows,
        "total_income": total_income,
        "total_expense": total_expense,
        "total_balance": total_balance,
        "statement_date": timezone.localdate(),
    }

    return render(request, "employees/ledger_statement.html", context)


def select_expense_statement_params(request):
    """Parameters page for Expense Statement"""
    if request.method == "POST":
        session_id = request.POST.get("session")
        return redirect(f"/employees/expense-statement/?session={session_id}")

    sessions = Session.objects.all().order_by("-session")
    return render(request, "employees/select_expense_statement_params.html", {"sessions": sessions})


def expense_statement(request):
    """Expense Statement - list expenses by month and head within a session"""
    session_id = request.GET.get("session")
    session = get_object_or_404(Session, pk=session_id) if session_id else None

    if not session_id:
        return redirect("select_expense_statement_params")

    zero = Decimal("0")
    # Group expenses by (month, head)
    groups = {}
    expenses = Expense.objects.filter(session_id=session_id).order_by("date")

    for exp in expenses:
        month_key = exp.date.strftime("%Y-%m")
        try:
            month_label = datetime.strptime(month_key, "%Y-%m").strftime("%B %Y")
        except (ValueError, TypeError):
            month_label = month_key
        head_name = exp.head or "—"
        key = (month_key, head_name)
        if key not in groups:
            groups[key] = {"month_label": month_label, "head": head_name, "amount": zero}
        groups[key]["amount"] += exp.amount or zero

    # Sort by month ascending, then head alphabetically
    sorted_items = sorted(groups.items(), key=lambda k: (k[0][0], k[0][1] or ""))
    rows = []
    for (_, _), data in sorted_items:
        rows.append({
            "session": session.session,
            "month_label": data["month_label"],
            "head": data["head"],
            "amount": data["amount"],
        })

    context = {
        "session": session,
        "rows": rows,
        "statement_date": timezone.localdate(),
    }

    return render(request, "employees/expense_statement.html", context)


def select_income_statement_params(request):
    """Parameters page for Income Statement"""
    if request.method == "POST":
        session_id = request.POST.get("session")
        month = request.POST.get("month")
        major_head = request.POST.get("major_head")
        
        url = f"/employees/income-statement/?session={session_id}"
        if month:
            url += f"&month={month}"
        if major_head:
            url += f"&major_head={major_head}"
        return redirect(url)

    sessions = Session.objects.all().order_by("-session")
    major_heads = Income.objects.values_list("major_head", flat=True).distinct().order_by("major_head")
    return render(request, "employees/select_income_statement_params.html", {
        "sessions": sessions,
        "major_heads": major_heads
    })


def income_statement(request):
    """Income Statement - list income by month and major head within a session"""
    session_id = request.GET.get("session")
    month = request.GET.get("month")
    major_head = request.GET.get("major_head")
    
    session = get_object_or_404(Session, pk=session_id) if session_id else None

    if not session_id:
        return redirect("select_income_statement_params")

    zero = Decimal("0")
    # Filter incomes
    incomes = Income.objects.filter(session_id=session_id).order_by("date")
    
    if month:
        incomes = incomes.filter(date__startswith=month)
    
    if major_head:
        incomes = incomes.filter(major_head=major_head)

    # Group incomes by (month, major_head)
    groups = {}
    for inc in incomes:
        month_key = inc.date.strftime("%Y-%m")
        try:
            month_label = datetime.strptime(month_key, "%Y-%m").strftime("%B %Y")
        except (ValueError, TypeError):
            month_label = month_key
        major_head_name = inc.major_head or "—"
        key = (month_key, major_head_name)
        if key not in groups:
            groups[key] = {"month_label": month_label, "major_head": major_head_name, "amount": zero}
        groups[key]["amount"] += inc.amount or zero

    # Sort by month ascending (Jan → Dec), then major head alphabetically
    sorted_items = sorted(groups.items(), key=lambda k: (k[0][0], k[0][1] or ""))
    rows = []
    for (_, _), data in sorted_items:
        rows.append({
            "session": session.session,
            "month_label": data["month_label"],
            "major_head": data["major_head"],
            "amount": data["amount"],
        })

    context = {
        "session": session,
        "rows": rows,
        "statement_date": timezone.localtime(),
        "selected_month": month,
        "selected_major_head": major_head,
    }

    return render(request, "employees/income_statement.html", context)


def full_statement(request):
    """Full Statement - all sessions with monthly income, expense, and balance"""
    # Group transactions by session and month
    session_month_data = {}
    zero = Decimal("0")

    # Fetch all transactions
    all_transactions = Expense.objects.all().order_by("session", "date")

    for transaction in all_transactions:
        session_name = transaction.session.session if transaction.session else "—"
        month_key = transaction.date.strftime("%Y-%m")
        try:
            month_label = datetime.strptime(month_key, "%Y-%m").strftime("%B %Y")
        except (ValueError, TypeError):
            month_label = month_key

        key = (session_name, month_key)
        if key not in session_month_data:
            session_month_data[key] = {
                "session": session_name,
                "month_label": month_label,
                "income": zero,
                "expense": zero,
            }

        if transaction.ledger_type == "Income":
            session_month_data[key]["income"] += transaction.amount
        elif transaction.ledger_type == "Expense":
            session_month_data[key]["expense"] += transaction.amount

    # Sort by session and month
    sorted_items = sorted(session_month_data.items(), key=lambda x: (x[0][0], x[0][1]))
    rows = []
    total_income = zero
    total_expense = zero

    for (_, _), data in sorted_items:
        balance = data["income"] - data["expense"]
        rows.append({
            "session": data["session"],
            "month_label": data["month_label"],
            "income": data["income"],
            "expense": data["expense"],
            "balance": balance,
        })
        total_income += data["income"]
        total_expense += data["expense"]

    total_balance = total_income - total_expense

    context = {
        "rows": rows,
        "total_income": total_income,
        "total_expense": total_expense,
        "total_balance": total_balance,
        "statement_date": timezone.localdate(),
    }

    return render(request, "employees/full_statement.html", context)


def select_full_statement_params(request):
    """Parameters page for Full Statement"""
    if request.method == "POST":
        return redirect("full_statement")

    return render(request, "employees/select_full_statement_params.html")

def employee_attendance(request):
    """View all employee attendance and add/edit attendance on same page"""
    editing_attendance = None
    form = None
    
    # Check if editing an attendance record
    edit_id = request.GET.get('edit')
    if edit_id:
        editing_attendance = get_object_or_404(EmployeeAttendance, pk=edit_id)
    
    if request.method == 'POST':
        if edit_id:
            # Editing existing attendance
            form = EmployeeAttendanceForm(request.POST, instance=editing_attendance)
        else:
            # Adding new attendance
            form = EmployeeAttendanceForm(request.POST)
        
        if form.is_valid():
            form.save()
            messages.success(request, f'Attendance {"updated" if edit_id else "added"} successfully!')
            return redirect('employee_attendance')
    else:
        if edit_id:
            form = EmployeeAttendanceForm(instance=editing_attendance)
        else:
            form = EmployeeAttendanceForm()
    
    attendance_records = EmployeeAttendance.objects.all().order_by('-date', 'employee__name')
    return render(request, 'employees/employee_attendance.html', {
        'attendance_records': attendance_records,
        'form': form,
        'editing_attendance': editing_attendance
    })


def delete_attendance(request, pk):
    """Delete an attendance record"""
    attendance = get_object_or_404(EmployeeAttendance, pk=pk)
    if request.method == 'POST':
        attendance.delete()
        messages.success(request, 'Attendance record deleted successfully!')
        return redirect('employee_attendance')
    
    return render(request, 'employees/delete_attendance.html', {'attendance': attendance})


def attendance_rally(request):
    """Attendance rally for marking all employees at once with radio buttons"""
    if request.method == 'POST':
        session_id = request.POST.get('session')
        date = request.POST.get('date')
        session = get_object_or_404(Session, pk=session_id)
        
        # Get all active employees
        employees = Employee.objects.filter(status='active').order_by('name')
        
        # Process attendance for each employee
        for employee in employees:
            attendance_value = request.POST.get(f'attendance_{employee.id}')
            if attendance_value:
                obj, created = EmployeeAttendance.objects.update_or_create(
                    session=session,
                    date=date,
                    employee=employee,
                    defaults={'attendance': attendance_value}
                )
        
        messages.success(request, 'Attendance marked successfully!')
        return redirect(f'attendance_rally')
    
    # Get active/current session as default
    sessions = Session.objects.all().order_by('-session')
    current_session = Session.objects.filter(status='current_session').first()
    
    # If no current session, use the first available one
    if not current_session and sessions.exists():
        current_session = sessions.first()
    
    # Allow override via GET parameter
    selected_session = request.GET.get('session')
    if selected_session:
        current_session = get_object_or_404(Session, pk=selected_session)
    
    # Get all active employees ordered by name
    employees = Employee.objects.filter(status='active').order_by('name')
    
    # Get today's date for default
    from datetime import date as date_class
    today = date_class.today()
    selected_date_str = request.GET.get('date', today.isoformat())
    
    # Convert string to date object for template formatting
    try:
        selected_date = date_class.fromisoformat(selected_date_str)
    except (ValueError, TypeError):
        selected_date = today
    
    # Get existing attendance records for the selected date if session is selected
    attendance_records = {}
    if current_session:
        records = EmployeeAttendance.objects.filter(
            session=current_session,
            date=selected_date
        ).values('employee_id', 'attendance')
        attendance_records = {r['employee_id']: r['attendance'] for r in records}
    
    context = {
        'sessions': sessions,
        'current_session': current_session,
        'employees': employees,
        'selected_date': selected_date,
        'selected_date_str': selected_date_str,
        'attendance_records': attendance_records,
    }
    
    return render(request, 'employees/attendance_rally.html', context)


@role_required('accountant', 'admin', 'teacher')
def employee_salary_statement(request, emp_id):
    """Generate salary statement for an employee reconciling payable vs paid amounts"""
    employee = get_object_or_404(Employee, pk=emp_id)
    
    # Get all ManualSalaryData entries (payable/due amounts)
    payable_entries = ManualSalaryData.objects.filter(
        employee=employee
    ).order_by('-month', '-created_at').values(
        'id', 'month', 'amount', 'amount_type', 'note', 'created_at'
    )
    
    # Get all Expense ledger entries (paid amounts) for this employee
    paid_entries = Expense.objects.filter(
        account_type='employee',
        employee=employee,
        ledger_type='Expense'
    ).order_by('-date').values(
        'id', 'date', 'amount', 'voucher_number', 'details'
    )
    
    # Group payable by month
    payable_by_month = {}
    total_payable = Decimal('0')
    for entry in payable_entries:
        month = entry['month']
        if month not in payable_by_month:
            payable_by_month[month] = {
                'entries': [],
                'total': Decimal('0'),
            }
        payable_by_month[month]['entries'].append(entry)
        payable_by_month[month]['total'] += Decimal(str(entry['amount']))
        total_payable += Decimal(str(entry['amount']))
    
    # Group paid by month
    paid_by_month = {}
    total_paid = Decimal('0')
    for entry in paid_entries:
        month = entry['date'].strftime('%Y-%m')
        if month not in paid_by_month:
            paid_by_month[month] = {
                'entries': [],
                'total': Decimal('0'),
            }
        paid_by_month[month]['entries'].append(entry)
        paid_by_month[month]['total'] += Decimal(str(entry['amount']))
        total_paid += Decimal(str(entry['amount']))
    
    # Reconcile: create a combined statement
    all_months = sorted(set(payable_by_month.keys()) | set(paid_by_month.keys()), reverse=True)
    
    statement = []
    for month in all_months:
        payable_data = payable_by_month.get(month, {'entries': [], 'total': Decimal('0')})
        paid_data = paid_by_month.get(month, {'entries': [], 'total': Decimal('0')})
        
        payable_total = payable_data['total']
        paid_total = paid_data['total']
        pending = payable_total - paid_total
        
        statement.append({
            'month': month,
            'payable_entries': payable_data['entries'],
            'payable_total': payable_total,
            'paid_entries': paid_data['entries'],
            'paid_total': paid_total,
            'pending': pending,
            'status': 'Paid' if pending <= 0 else ('Partial' if paid_total > 0 else 'Pending'),
        })
    
    # Calculate totals
    total_pending = total_payable - total_paid
    
    context = {
        'employee': employee,
        'statement': statement,
        'total_payable': total_payable,
        'total_paid': total_paid,
        'total_pending': total_pending,
    }
    
    return render(request, 'employees/transaction_salary_statement.html', context)


def employee_salary_payment_details(request, emp_id):
    """Generate detailed salary payment details for an employee showing all individual payments"""
    employee = get_object_or_404(Employee, pk=emp_id)
    
    # Get all ManualSalaryData entries (payable/due amounts) grouped by month
    payable_by_month = {}
    payable_entries = ManualSalaryData.objects.filter(
        employee=employee
    ).order_by('-month', '-created_at')
    
    for entry in payable_entries:
        month = entry.month
        if month not in payable_by_month:
            payable_by_month[month] = Decimal('0')
        payable_by_month[month] += entry.amount
    
    # Get all Expense ledger entries (paid amounts) for this employee
    paid_entries = Expense.objects.filter(
        account_type='employee',
        employee=employee,
        ledger_type='Expense'
    ).order_by('-date')
    
    # Build detailed payment list with each transaction as a separate row
    payment_details = []
    total_payable = Decimal('0')
    total_paid = Decimal('0')
    
    for paid_entry in paid_entries:
        month = paid_entry.date.strftime('%Y-%m')
        session = paid_entry.session.session if paid_entry.session else 'N/A'
        payable = payable_by_month.get(month, Decimal('0'))
        
        total_payable += payable if month not in [p['month'] for p in payment_details] else Decimal('0')
        total_paid += paid_entry.amount
        
        # Calculate pending for this month
        month_payments = Decimal(str(sum(
            p['amount'] for p in payment_details if p['month'] == month
        )))
        pending = payable - (month_payments + paid_entry.amount)
        
        payment_details.append({
            'session': session,
            'month': month,
            'payable': payable,
            'payment_date': paid_entry.date,
            'amount': paid_entry.amount,
            'voucher': paid_entry.voucher_number,
            'details': paid_entry.details,
            'pending': pending,
        })
    
    # Add any months with payable but no payments
    for month, payable in sorted(payable_by_month.items(), reverse=True):
        if month not in [p['month'] for p in payment_details]:
            session = 'N/A'
            # Try to find session from ManualSalaryData
            salary_entry = ManualSalaryData.objects.filter(
                employee=employee, month=month
            ).first()
            if salary_entry and salary_entry.session:
                session = salary_entry.session.session
            
            total_payable += payable
            payment_details.append({
                'session': session,
                'month': month,
                'payable': payable,
                'payment_date': None,
                'amount': Decimal('0'),
                'voucher': '-',
                'details': 'Not Paid',
                'pending': payable,
            })
    
    # Sort by month and date
    payment_details.sort(key=lambda x: (x['month'], x['payment_date'] or ''), reverse=True)
    
    total_pending = total_payable - total_paid
    
    context = {
        'employee': employee,
        'payment_details': payment_details,
        'total_payable': total_payable,
        'total_paid': total_paid,
        'total_pending': total_pending,
    }
    
    return render(request, 'employees/salary_payment_details.html', context)


def employee_salary_statement(request):
    """Generate complete salary statement for an employee"""
    sessions = Session.objects.all().order_by('-session')
    employees_list = Employee.objects.all().order_by('name')
    
    selected_session = None
    selected_employee = None
    employee_info = {}
    monthly_salary_data = []
    payment_transactions = []
    summary = {}
    
    selected_session_id = request.GET.get('session')
    selected_employee_id = request.GET.get('employee')
    
    if selected_session_id and selected_employee_id:
        try:
            selected_session = Session.objects.get(id=selected_session_id)
            selected_employee = Employee.objects.get(id=selected_employee_id)
            
            # Panel 1: Employee Info
            employee_info = {
                'name': selected_employee.name,
                'post': selected_employee.post,
                'session': selected_session.session,
                'status': selected_employee.get_status_display(),
            }
            
            # Get old dues from ManualSalaryData
            old_dues = ManualSalaryData.objects.filter(
                session=selected_session,
                employee=selected_employee,
                amount_type='old_due'
            ).aggregate(total=Sum('amount'))['total'] or 0
            
            # Panel 2: Monthly Salary Schedule from ManualSalaryData
            # Financial year: April-March
            financial_months = [
                ('April', 4), ('May', 5), ('June', 6),
                ('July', 7), ('August', 8), ('September', 9),
                ('October', 10), ('November', 11), ('December', 12),
                ('January', 1), ('February', 2), ('March', 3)
            ]
            month_name_map = {
                1: 'January', 2: 'February', 3: 'March', 4: 'April',
                5: 'May', 6: 'June', 7: 'July', 8: 'August',
                9: 'September', 10: 'October', 11: 'November', 12: 'December'
            }
            
            # Get the financial year from session
            # Assuming session format is like "2024-2025" or similar
            session_year = int(selected_session.session.split('-')[0]) if '-' in selected_session.session else datetime.now().year
            
            # Query all ManualSalaryData records for this employee (all types: salary, old_due, other)
            all_salary_records = ManualSalaryData.objects.filter(
                session=selected_session,
                employee=selected_employee
            ).order_by('month')
            
            for record in all_salary_records:
                # Extract year and month from the month field (format: YYYY-MM)
                try:
                    record_year, record_month_num = map(int, record.month.split('-'))
                    month_name = month_name_map.get(record_month_num, record.month)
                except (ValueError, AttributeError):
                    # Fallback if month field is not in expected format
                    record_year = ''
                    month_name = record.month
                
                monthly_salary_data.append({
                    'month': month_name,
                    'year': record_year,
                    'salary_to_pay': float(record.amount),
                    'payment_type': record.get_amount_type_display(),
                    'notes': record.note or '',
                })
            
            # Add fallback salary entries for months without ManualSalaryData records
            for month_name, month_num in financial_months:
                # Check if we already have a salary record for this month
                has_record = any(
                    record.month.endswith(f'-{month_num:02d}') 
                    for record in all_salary_records
                )
                
                if not has_record:
                    # For April-December, use the session_year; for January-March, use session_year + 1
                    year_for_month = session_year if month_num >= 4 else session_year + 1
                    
                    # Fallback to EmployeeRegister if available
                    base_salary_entry = EmployeeRegister.objects.filter(
                        session=selected_session,
                        employee=selected_employee
                    ).first()
                    monthly_amount = float(base_salary_entry.payable_salary) if base_salary_entry else float(selected_employee.base_salary_per_month or 0)
                    
                    monthly_salary_data.append({
                        'month': month_name,
                        'year': year_for_month,
                        'salary_to_pay': monthly_amount,
                        'payment_type': 'Salary',
                        'notes': '',
                    })
            
            # Panel 3: Actual Payment Transactions
            # Query Expense table where Major Head = "Salary" and Sub Head (account_name) = Employee name
            payment_transactions = Expense.objects.filter(
                session=selected_session,
                major_head='Salary',
                sub_head=selected_employee.name
            ).values('date', 'details', 'amount').order_by('date')
            
            # Convert QuerySet to list of dicts with proper formatting
            transactions_list = []
            total_paid = 0
            month_name_map_short = {
                1: 'January', 2: 'February', 3: 'March', 4: 'April',
                5: 'May', 6: 'June', 7: 'July', 8: 'August',
                9: 'September', 10: 'October', 11: 'November', 12: 'December'
            }
            for txn in payment_transactions:
                txn_date = txn['date']
                txn_year = txn_date.year
                txn_month_num = txn_date.month
                txn_month_name = month_name_map_short.get(txn_month_num, str(txn_month_num))
                
                transactions_list.append({
                    'date': txn_date.strftime('%d/%m/%Y'),
                    'year': txn_year,
                    'month': txn_month_name,
                    'remarks': txn['details'] or '',
                    'amount': float(txn['amount']),
                })
                total_paid += float(txn['amount'])
            
            payment_transactions = transactions_list
            
            # Calculate totals - sum all amounts from monthly_salary_data which already includes everything
            total_salary_due = sum(m['salary_to_pay'] for m in monthly_salary_data)
            # Total Due = Total Paid - Total Salary Due (negative means still owed)
            total_due = total_paid - total_salary_due
            
            # Get average monthly salary for display (only salary records, not old_due or other)
            salary_records_only = [m for m in monthly_salary_data if m['payment_type'] == 'Salary']
            avg_monthly_salary = sum(m['salary_to_pay'] for m in salary_records_only) / len(salary_records_only) if salary_records_only else 0
            
            summary = {
                'old_dues': float(old_dues),
                'monthly_salary': avg_monthly_salary,
                'total_salary': total_salary_due,
                'total_paid': total_paid,
                'total_due': total_due,
            }
            
        except (Session.DoesNotExist, Employee.DoesNotExist):
            selected_session = None
            selected_employee = None
    
    context = {
        'sessions': sessions,
        'employees_list': employees_list,
        'selected_session': selected_session,
        'selected_employee': selected_employee,
        'selected_session_id': selected_session_id,
        'selected_employee_id': selected_employee_id,
        'employee_info': employee_info,
        'monthly_salary_data': monthly_salary_data,
        'payment_transactions': payment_transactions,
        'summary': summary,
    }
    
    return render(request, 'employees/employee_salary_statement.html', context)


@role_required('accountant', 'admin')
def employees_salary_statement(request):
    """Generate salary statement for all employees in a session"""
    sessions = Session.objects.all().order_by('-session')
    
    selected_session = None
    employee_rows = []
    totals = {
        'old_dues': 0,
        'salary_data': 0,
        'paid_amount': 0,
        'due': 0,
    }
    
    selected_session_id = request.GET.get('session')
    selected_status = request.GET.get('status')
    
    if selected_session_id:
        try:
            selected_session = Session.objects.get(id=selected_session_id)
            
            # Get all unique employees from ManualSalaryData for this session
            employees_in_session = Employee.objects.filter(
                manual_salary_records__session=selected_session
            ).distinct().order_by('name')
            
            # Apply status filter if selected
            if selected_status:
                employees_in_session = employees_in_session.filter(status=selected_status)
            
            for employee in employees_in_session:
                # Get old dues for this employee
                old_dues = ManualSalaryData.objects.filter(
                    session=selected_session,
                    employee=employee,
                    amount_type='old_due'
                ).aggregate(total=Sum('amount'))['total'] or 0
                
                # Get salary data for this employee (sum of all salary records)
                salary_data = ManualSalaryData.objects.filter(
                    session=selected_session,
                    employee=employee,
                    amount_type='salary'
                ).aggregate(total=Sum('amount'))['total'] or 0
                
                # Get paid amount from Expense table
                paid_amount = Expense.objects.filter(
                    session=selected_session,
                    major_head='Salary',
                    sub_head=employee.name
                ).aggregate(total=Sum('amount'))['total'] or 0
                
                # Calculate due = paid_amount - salary_data - old_dues
                due = float(paid_amount) - float(salary_data) - float(old_dues)
                
                employee_rows.append({
                    'employee_name': employee.name,
                    'employee_post': employee.post,
                    'employee_status': employee.get_status_display(),
                    'old_dues': float(old_dues),
                    'salary_data': float(salary_data),
                    'paid_amount': float(paid_amount),
                    'due': due,
                })
                
                # Add to totals
                totals['old_dues'] += float(old_dues)
                totals['salary_data'] += float(salary_data)
                totals['paid_amount'] += float(paid_amount)
                totals['due'] += due
                
        except Session.DoesNotExist:
            selected_session = None
    
    context = {
        'sessions': sessions,
        'selected_session': selected_session,
        'selected_session_id': selected_session_id,
        'selected_status': selected_status,
        'status_choices': Employee.STATUS_CHOICES,
        'employee_rows': employee_rows,
        'totals': totals,
    }
    
    return render(request, 'employees/employees_salary_statement.html', context)


def export_employees_csv(request):
    """Export all employees to CSV in bulk import format"""
    employees = Employee.objects.all()
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="employees.csv"'
    
    writer = csv.writer(response)
    # Headers must match the bulk import format
    writer.writerow(['Name', 'DOB', 'Contact_Number', 'Gender', 'Qualification', 'Address', 'Experience_Years', 'Previous_Institute', 'Post', 'Role', 'Role_Detail', 'Joining_Date', 'Base_Salary_Per_Month', 'Status', 'Leaves_Entitled'])
    
    for employee in employees:
        writer.writerow([
            employee.name,
            employee.dob.strftime('%Y-%m-%d') if employee.dob else '',
            employee.contact_number or '',
            employee.gender or '',
            employee.qualification or '',
            employee.address or '',
            employee.experience_years or '',
            employee.previous_institute or '',
            employee.post or '',
            employee.role or '',
            employee.role_detail or '',
            employee.joining_date.strftime('%Y-%m-%d') if employee.joining_date else '',
            employee.base_salary_per_month,
            employee.status,
            employee.leaves_entitled,
        ])
    
    return response


def delete_all_employees(request):
    """Delete all employees with confirmation"""
    if request.method == 'POST':
        count, _ = Employee.objects.all().delete()
        messages.success(request, f'Successfully deleted {count} employee records.')
        return redirect('employees_home')
    
    # Show confirmation page
    employee_count = Employee.objects.count()
    return render(request, 'employees/confirm_delete_all.html', {
        'item_type': 'Employees',
        'item_count': employee_count,
        'delete_url': 'delete_all_employees'
    })
