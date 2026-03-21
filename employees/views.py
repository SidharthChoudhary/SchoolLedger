import csv

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.db.models import Sum
from django.contrib import messages
from accounts.decorators import role_required
from django.views.decorators.cache import never_cache

from .models import Employee, EmployeeRegister, EmployeeAttendance, ManualSalaryData
from .forms import EmployeeForm, EmployeeRegisterForm, EmployeeAttendanceForm, ManualSalaryDataForm
from dailyLedger.models import Session, Expense

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


def employee_profile(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    registers = EmployeeRegister.objects.filter(employee=employee).select_related("session").order_by("-month")
    return render(request, "employees/employee_profile.html", {
        "employee": employee,
        "registers": registers,
    })


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


def employees_salary_statement(request):
    """All-employees salary summary for a session — Old Due + Salary Amount + Paid + Net Due"""
    sessions = Session.objects.all().order_by('-session')
    default_session = Session.objects.filter(status='current_session').first() or sessions.first()
    selected_session_id = request.GET.get('session', str(default_session.id) if default_session else '')
    selected_status = request.GET.get('status', 'active')

    selected_session = Session.objects.filter(pk=selected_session_id).first() if selected_session_id else None

    rows = []
    total_old_due = 0
    total_salary = 0
    total_paid = 0

    if selected_session:
        emp_qs = Employee.objects.all().order_by('name')
        if selected_status:
            emp_qs = emp_qs.filter(status=selected_status)

        # Preload all old dues for this session
        old_due_map = {}
        for rec in ManualSalaryData.objects.filter(session=selected_session, amount_type='old_due').values('employee_id', 'amount'):
            old_due_map.setdefault(rec['employee_id'], 0)
            old_due_map[rec['employee_id']] += rec['amount']

        # Preload all EmployeeRegister entries for this session to get payable salaries
        register_map = {}
        for reg in EmployeeRegister.objects.filter(session=selected_session).values('employee_id', 'payable_salary'):
            register_map.setdefault(reg['employee_id'], 0)
            register_map[reg['employee_id']] += reg['payable_salary']

        # Preload all expenses for this session
        paid_map = {}
        for exp in Expense.objects.filter(session=selected_session, employee__isnull=False).values('employee_id', 'amount'):
            paid_map.setdefault(exp['employee_id'], 0)
            paid_map[exp['employee_id']] += exp['amount']

        for emp in emp_qs:
            old_due = old_due_map.get(emp.id, 0)
            # Use EmployeeRegister total if available, otherwise base_salary * 12
            salary_amount = register_map.get(emp.id) or (emp.base_salary_per_month * 12)
            paid = paid_map.get(emp.id, 0)
            net_due = (old_due + salary_amount) - paid
            rows.append({
                'employee': emp,
                'old_due': old_due,
                'salary_amount': salary_amount,
                'paid': paid,
                'net_due': net_due,
            })
            total_old_due += old_due
            total_salary += salary_amount
            total_paid += paid

    total_net_due = (total_old_due + total_salary) - total_paid

    return render(request, 'employees/employees_salary_statement.html', {
        'sessions': sessions,
        'selected_session': selected_session,
        'selected_session_id': selected_session_id,
        'selected_status': selected_status,
        'status_choices': Employee.STATUS_CHOICES,
        'rows': rows,
        'total_old_due': total_old_due,
        'total_salary': total_salary,
        'total_paid': total_paid,
        'total_net_due': total_net_due,
    })


def employee_full_salary_statement(request):
    """Employee Full Salary Statement - monthly schedule + payment transactions + summary"""
    from calendar import month_name as cal_month_name

    sessions = Session.objects.all().order_by('-session')
    employees = Employee.objects.all().order_by('name')

    default_session = Session.objects.filter(status='current_session').first() or sessions.first()
    selected_session_id = request.GET.get('session', str(default_session.id) if default_session else '')
    selected_employee_id = request.GET.get('employee', '')

    selected_session = None
    selected_employee = None
    monthly_schedule = []
    payment_transactions = []
    total_salary_due = 0
    total_paid = 0
    old_dues = 0
    monthly_total = 0
    base_salary = 0

    if selected_session_id:
        selected_session = Session.objects.filter(pk=selected_session_id).first()

    if selected_employee_id and selected_session:
        selected_employee = Employee.objects.filter(pk=selected_employee_id).first()

    if selected_session and selected_employee:
        base_salary = selected_employee.base_salary_per_month or 0

        # Parse session "2025-2026" -> start_year=2025, end_year=2026
        try:
            parts = selected_session.session.split('-')
            start_year = int(parts[0])
            end_year = int(parts[1])
        except (ValueError, IndexError):
            from datetime import date as date_cls
            start_year = date_cls.today().year
            end_year = start_year + 1

        # Financial year: April to March
        fin_months = [
            (start_year, 4), (start_year, 5), (start_year, 6),
            (start_year, 7), (start_year, 8), (start_year, 9),
            (start_year, 10), (start_year, 11), (start_year, 12),
            (end_year, 1), (end_year, 2), (end_year, 3),
        ]

        register_map = {
            r.month: r
            for r in EmployeeRegister.objects.filter(
                session=selected_session, employee=selected_employee
            )
        }

        expenses = list(Expense.objects.filter(
            employee=selected_employee, session=selected_session
        ).order_by('date'))

        expense_by_month = {}
        for exp in expenses:
            key = f"{exp.date.year}-{exp.date.month:02d}"
            expense_by_month.setdefault(key, []).append(exp)

        for (yr, mo) in fin_months:
            month_key = f"{yr}-{mo:02d}"
            register = register_map.get(month_key)
            amount = register.payable_salary if register else base_salary
            paid = sum(e.amount for e in expense_by_month.get(month_key, []))
            monthly_schedule.append({
                'year': yr,
                'month': cal_month_name[mo],
                'payment_type': 'Salary',
                'notes': '',
                'amount': amount,
                'paid': paid,
                'net_due': amount - paid,
            })

        old_due_qs = ManualSalaryData.objects.filter(
            employee=selected_employee, session=selected_session, amount_type='old_due'
        )
        old_dues = sum(r.amount for r in old_due_qs)
        monthly_total = sum(r['amount'] for r in monthly_schedule)
        total_salary_due = monthly_total + old_dues
        total_paid = sum(r['paid'] for r in monthly_schedule)

        payment_transactions = [
            {
                'year': exp.date.year,
                'month': exp.date.strftime('%B'),
                'payment_date': exp.date,
                'remarks': exp.details,
                'amount': exp.amount,
            }
            for exp in expenses
        ]

    return render(request, 'employees/employee_full_salary_statement.html', {
        'sessions': sessions,
        'employees': employees,
        'selected_session': selected_session,
        'selected_session_id': selected_session_id,
        'selected_employee': selected_employee,
        'selected_employee_id': selected_employee_id,
        'monthly_schedule': monthly_schedule,
        'payment_transactions': payment_transactions,
        'total_salary_due': total_salary_due,
        'total_paid': total_paid,
        'net_due': total_salary_due - total_paid,
        'old_dues': old_dues,
        'monthly_total': monthly_total,
        'base_salary': base_salary,
    })
