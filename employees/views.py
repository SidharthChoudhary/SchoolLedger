import csv

from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.db.models import Sum, Case, When, Value, IntegerField
from django.contrib import messages
from accounts.decorators import role_required
from django.views.decorators.cache import never_cache

from .models import Employee, EmployeeAttendance, EmployeePayrollEntry
from .forms import EmployeeForm, EmployeeAttendanceForm
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
    writer.writerow(['Emp_No', 'Name', 'DOB', 'Contact_Number', 'Gender', 'Qualification', 'Address', 'Experience_Years', 'Previous_Institute', 'Post', 'Role', 'Role_Detail', 'Joining_Date', 'Base_Salary_Per_Month', 'Status', 'Leaves_Entitled'])
    
    # Sample rows (Emp_No is optional — leave blank to auto-assign)
    writer.writerow(['1001', 'John Smith', '1990-05-20', '9876543210', 'M', 'B.Ed', '123 Main Street', '5', 'XYZ School', 'Teacher', 'Class Teacher', 'Class 5A', '2022-01-15', '50000', 'active', '30'])
    writer.writerow(['1002', 'Jane Doe', '1988-03-15', '9876543211', 'F', 'M.Sc', '456 Oak Avenue', '8.5', 'ABC Institute', 'Senior Teacher', 'Subject Head', 'Mathematics Department', '2020-06-01', '65000', 'active', '25'])
    writer.writerow(['', 'Robert Johnson', '1992-07-10', '9876543212', 'M', 'B.Com', '789 Pine Road', '3', 'MNO College', 'Accountant', 'Staff', 'Finance Department', '2023-04-20', '40000', 'active', '30'])
    
    return response



def employees_view(request):
    employees = Employee.objects.all().annotate(
        status_order=Case(
            When(status='active', then=Value(0)),
            When(status='left', then=Value(1)),
            When(status='inactive', then=Value(2)),
            default=Value(3),
            output_field=IntegerField(),
        )
    ).order_by('status_order', 'name')

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
    payroll_entries = EmployeePayrollEntry.objects.filter(employee=employee).select_related('session').order_by('-month')
    return render(request, 'employees/employee_profile.html', {
        'employee': employee,
        'registers': payroll_entries,
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


def attendance_register(request):
    """View attendance register with filters on month, employee name, and status"""
    from datetime import date as date_class

    sessions = Session.objects.all().order_by('-session')
    employees_list = Employee.objects.filter(status='active').order_by('name')

    # --- read filters ---
    selected_session_id = request.GET.get('session', '')
    selected_month = request.GET.get('month', '')        # YYYY-MM
    selected_employee = request.GET.get('employee', '')  # employee id
    selected_status = request.GET.get('attendance', '')  # present/absent/half-day/leave

    # default session
    current_session = Session.objects.filter(status='current_session').first()
    if not current_session and sessions.exists():
        current_session = sessions.first()
    if selected_session_id:
        current_session = Session.objects.filter(pk=selected_session_id).first() or current_session

    qs = EmployeeAttendance.objects.select_related('employee', 'session').order_by('-date', 'employee__name')

    if current_session:
        qs = qs.filter(session=current_session)

    if selected_month:
        try:
            year, month = selected_month.split('-')
            qs = qs.filter(date__year=int(year), date__month=int(month))
        except ValueError:
            pass

    if selected_employee:
        qs = qs.filter(employee_id=selected_employee)

    if selected_status:
        qs = qs.filter(attendance=selected_status)

    # summary counts for the filtered queryset
    from django.db.models import Count
    total = qs.count()
    status_counts = {
        item['attendance']: item['count']
        for item in qs.values('attendance').annotate(count=Count('id'))
    }

    # Monthly Register Salary summary — shown when a month is selected
    salary_summary = []
    days_in_month = None
    if selected_month and current_session:
        from calendar import monthrange
        try:
            yr, mo = selected_month.split('-')
            _, days_in_month = monthrange(int(yr), int(mo))

            # Base qs: session + month only — no employee/status filter so we get full per-employee picture
            summary_base = EmployeeAttendance.objects.filter(
                session=current_session,
                date__year=int(yr),
                date__month=int(mo),
            )

            summary_emps = employees_list
            if selected_employee:
                summary_emps = summary_emps.filter(pk=selected_employee)

            for emp in summary_emps:
                emp_qs = summary_base.filter(employee=emp)
                present  = emp_qs.filter(attendance='present').count()
                halfday  = emp_qs.filter(attendance='half-day').count()
                leave    = emp_qs.filter(attendance='leave').count()
                absent   = emp_qs.filter(attendance='absent').count()

                monthly_salary = float(emp.base_salary_per_month or 0)
                present_days   = present + halfday * 0.5

                if leave <= 2:
                    register_salary = monthly_salary
                else:
                    salary_per_day  = monthly_salary / days_in_month if days_in_month else 0
                    register_salary = round(salary_per_day * present_days, 2)

                salary_summary.append({
                    'employee': emp,
                    'present': present,
                    'halfday': halfday,
                    'leave': leave,
                    'absent': absent,
                    'monthly_salary': monthly_salary,
                    'register_salary': register_salary,
                })
        except (ValueError, TypeError):
            pass

    context = {
        'sessions': sessions,
        'current_session': current_session,
        'employees_list': employees_list,
        'records': qs,
        'selected_month': selected_month,
        'selected_employee': selected_employee,
        'selected_status': selected_status,
        'total': total,
        'count_present': status_counts.get('present', 0),
        'count_absent': status_counts.get('absent', 0),
        'count_halfday': status_counts.get('half-day', 0),
        'count_leave': status_counts.get('leave', 0),
        'attendance_choices': EmployeeAttendance.ATTENDANCE_CHOICES,
        'salary_summary': salary_summary,
        'days_in_month': days_in_month,
        'total_monthly_salary': sum(r['monthly_salary'] for r in salary_summary),
        'total_register_salary': sum(r['register_salary'] for r in salary_summary),
    }
    return render(request, 'employees/attendance_register.html', context)


def delete_filtered_attendance(request):
    """Delete all attendance records matching the current filter (POST only)"""
    if request.method != 'POST':
        return redirect('attendance_register')
    session_id      = request.POST.get('session', '')
    selected_month  = request.POST.get('month', '')
    selected_employee = request.POST.get('employee', '')
    selected_status = request.POST.get('attendance', '')

    current_session = Session.objects.filter(pk=session_id).first() if session_id else None
    qs = EmployeeAttendance.objects.all()
    if current_session:
        qs = qs.filter(session=current_session)
    if selected_month:
        try:
            year, month = selected_month.split('-')
            qs = qs.filter(date__year=int(year), date__month=int(month))
        except ValueError:
            pass
    if selected_employee:
        qs = qs.filter(employee_id=selected_employee)
    if selected_status:
        qs = qs.filter(attendance=selected_status)

    count, _ = qs.delete()
    messages.success(request, f'{count} attendance record(s) deleted.')
    params = []
    if session_id:        params.append(f'session={session_id}')
    if selected_month:    params.append(f'month={selected_month}')
    if selected_employee: params.append(f'employee={selected_employee}')
    if selected_status:   params.append(f'attendance={selected_status}')
    qs_str = '&'.join(params)
    return redirect(f"/employees/attendance-register/?{qs_str}" if qs_str else '/employees/attendance-register/')


def import_attendance_csv(request):
    """Import attendance records from a CSV file (date, employee_name, attendance)"""
    if request.method == 'POST':
        session_id = request.POST.get('session')
        csv_file = request.FILES.get('csv_file')
        redirect_date = request.POST.get('redirect_date', '')
        redirect_session = session_id

        if not csv_file:
            messages.error(request, 'Please select a CSV file to import.')
            return redirect('attendance_rally')

        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Only CSV files are supported.')
            return redirect('attendance_rally')

        session = get_object_or_404(Session, pk=session_id)

        try:
            decoded = csv_file.read().decode('utf-8-sig')  # utf-8-sig handles BOM from Excel
            reader = csv.DictReader(decoded.splitlines())
            valid_statuses = {'present', 'absent', 'half-day', 'leave'}
            imported = 0
            error_list = []

            from datetime import date as date_class
            for i, row in enumerate(reader, start=2):
                date_str = (row.get('date') or '').strip()
                employee_name = (row.get('employee_name') or '').strip()
                attendance_value = (row.get('attendance') or '').strip().lower()

                if not date_str or not employee_name or not attendance_value:
                    error_list.append(f'Row {i}: Missing value(s) — skipped.')
                    continue

                if attendance_value not in valid_statuses:
                    error_list.append(f'Row {i}: Invalid attendance "{attendance_value}" — use present/absent/half-day/leave.')
                    continue

                try:
                    date_obj = date_class.fromisoformat(date_str)
                except ValueError:
                    error_list.append(f'Row {i}: Invalid date "{date_str}" — use YYYY-MM-DD format.')
                    continue

                employee = Employee.objects.filter(name__iexact=employee_name).first()
                if not employee:
                    error_list.append(f'Row {i}: Employee "{employee_name}" not found — check spelling.')
                    continue

                EmployeeAttendance.objects.update_or_create(
                    session=session,
                    date=date_obj,
                    employee=employee,
                    defaults={'attendance': attendance_value}
                )
                imported += 1
                if not redirect_date:
                    redirect_date = date_obj.isoformat()

            for err in error_list:
                messages.warning(request, err)

            messages.success(request, f'CSV import complete: {imported} record(s) saved.')

        except Exception as e:
            messages.error(request, f'Error reading CSV: {e}')

        url = f'/employees/attendance-rally/?session={redirect_session}'
        if redirect_date:
            url += f'&date={redirect_date}'
        return redirect(url)

    return redirect('attendance_rally')


def download_attendance_template(request):
    """Return a sample CSV template for attendance import with real employee names"""
    from datetime import date as date_class
    today = date_class.today().isoformat()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="attendance_import_template.csv"'
    writer = csv.writer(response)
    writer.writerow(['date', 'employee_name', 'attendance'])
    employees = Employee.objects.filter(status='active').order_by('name')[:5]
    sample_statuses = ['present', 'absent', 'half-day', 'leave', 'present']
    if employees.exists():
        for idx, emp in enumerate(employees):
            writer.writerow([today, emp.name, sample_statuses[idx % len(sample_statuses)]])
    else:
        writer.writerow([today, 'Employee Name', 'present'])
    return response


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
    writer.writerow(['Emp_No', 'Name', 'DOB', 'Contact_Number', 'Gender', 'Qualification', 'Address', 'Experience_Years', 'Previous_Institute', 'Post', 'Role', 'Role_Detail', 'Joining_Date', 'Base_Salary_Per_Month', 'Status', 'Leaves_Entitled'])
    
    for employee in employees:
        writer.writerow([
            employee.emp_no,
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


def employee_payroll_unified(request):
    """Unified payroll page: derive Register Salary from attendance, save Payable Salary manually"""
    from calendar import monthrange
    from django.db.models import Sum as DjSum

    sessions = Session.objects.all().order_by('-session')
    employees_list = Employee.objects.filter(status='active').order_by('name')

    # Resolve selected session
    selected_session_id = request.GET.get('session', '')
    selected_month = request.GET.get('month', '')
    current_session = Session.objects.filter(status='current_session').first()
    if not current_session and sessions.exists():
        current_session = sessions.first()
    if selected_session_id:
        current_session = Session.objects.filter(pk=selected_session_id).first() or current_session

    def _calc_old_dues(emp, session, before_month):
        """For April (first month of session): old dues = unpaid balance from the previous session.
           For other months: old dues = owed in current session before this month minus paid."""
        try:
            mo = before_month.split('-')[1]
        except (IndexError, AttributeError):
            mo = ''

        if mo == '04':
            # Find the previous session (session names like "2025-2026", ordered descending)
            prev_session = Session.objects.filter(
                session__lt=session.session
            ).order_by('-session').first()
            if not prev_session:
                return 0
            owed = EmployeePayrollEntry.objects.filter(
                session=prev_session, employee=emp
            ).aggregate(
                total_payable=DjSum('payable_salary'),
                total_other=DjSum('other_amount')
            )
            total_owed = float(owed['total_payable'] or 0) + float(owed['total_other'] or 0)
            paid = Expense.objects.filter(
                employee=emp, session=prev_session
            ).aggregate(total=DjSum('amount'))['total'] or 0
            return round(max(float(total_owed) - float(paid), 0), 2)
        else:
            past = EmployeePayrollEntry.objects.filter(
                session=session, employee=emp, month__lt=before_month
            ).aggregate(
                total_payable=DjSum('payable_salary'),
                total_other=DjSum('other_amount')
            )
            total_owed = float(past['total_payable'] or 0) + float(past['total_other'] or 0)
            paid = Expense.objects.filter(
                employee=emp, session=session
            ).aggregate(total=DjSum('amount'))['total'] or 0
            return round(max(float(total_owed) - float(paid), 0), 2)

    # ── POST: Generate Payroll ──────────────────────────────────────────────
    if request.method == 'POST' and request.POST.get('action') == 'generate':
        session_id = request.POST.get('session')
        month = request.POST.get('month')
        if not month:
            messages.error(request, 'Please select a month before generating payroll.')
            return redirect(f'/employees/payroll/?session={session_id}')

        session = get_object_or_404(Session, pk=session_id)
        try:
            yr, mo = month.split('-')
            _, days_in_month = monthrange(int(yr), int(mo))
        except (ValueError, TypeError):
            messages.error(request, 'Invalid month.')
            return redirect(f'/employees/payroll/?session={session_id}&month={month}')

        att_base = EmployeeAttendance.objects.filter(
            session=session, date__year=int(yr), date__month=int(mo)
        )
        created = 0
        updated = 0
        for emp in employees_list:
            present = att_base.filter(employee=emp, attendance='present').count()
            halfday = att_base.filter(employee=emp, attendance='half-day').count()
            leave   = att_base.filter(employee=emp, attendance='leave').count()
            work_days = present + halfday * 0.5
            # No records at all → treat entire month as leave
            if present == 0 and halfday == 0 and leave == 0:
                leave = days_in_month
            monthly_salary = float(emp.base_salary_per_month or 0)
            total_tracked = work_days + leave
            register_salary = monthly_salary if (leave <= 2 and total_tracked >= days_in_month - 2) else min(round((monthly_salary / 30) * work_days, 2), monthly_salary)
            # Old dues only apply in April (start of session)
            old_dues = _calc_old_dues(emp, session, month) if mo == '04' else 0

            obj, is_new = EmployeePayrollEntry.objects.get_or_create(
                session=session, employee=emp, month=month
            )
            obj.payable_salary = register_salary
            obj.old_dues = old_dues
            obj.save()
            if is_new:
                created += 1
            else:
                updated += 1

        messages.success(request, f'Payroll generated: {created} new, {updated} recalculated.')
        return redirect(f'/employees/payroll/?session={session_id}&month={month}')

    # ── POST: Save All ──────────────────────────────────────────────────────
    if request.method == 'POST' and request.POST.get('action') == 'save':
        session_id = request.POST.get('session')
        month = request.POST.get('month')
        session = get_object_or_404(Session, pk=session_id)
        # Determine if selected month is April
        try:
            _, _mo_save = month.split('-')
        except (ValueError, TypeError, AttributeError):
            _mo_save = ''
        saved = 0
        for emp in employees_list:
            payable_str      = request.POST.get(f'payable_{emp.id}', '').strip()
            # Old dues are only allowed in April; force 0 for all other months
            old_dues_str     = (request.POST.get(f'old_dues_{emp.id}', '').strip() or '0') if _mo_save == '04' else '0'
            other_str        = request.POST.get(f'other_{emp.id}', '').strip() or '0'
            note             = request.POST.get(f'note_{emp.id}', '').strip()
            manual_work_str  = request.POST.get(f'manual_work_{emp.id}', '').strip()
            manual_leave_str = request.POST.get(f'manual_leave_{emp.id}', '').strip()
            if payable_str == '' and old_dues_str == '0' and other_str == '0' and not note and not manual_work_str and not manual_leave_str:
                continue
            obj, _ = EmployeePayrollEntry.objects.get_or_create(
                session=session, employee=emp, month=month
            )
            try:
                obj.payable_salary  = float(payable_str) if payable_str != '' else obj.payable_salary
                obj.old_dues        = float(old_dues_str)
                obj.other_amount    = float(other_str)
                obj.note            = note
                obj.manual_work_days  = float(manual_work_str)  if manual_work_str  != '' else None
                obj.manual_leave_days = int(float(manual_leave_str)) if manual_leave_str != '' else None
                obj.save()
                saved += 1
            except (ValueError, TypeError):
                messages.warning(request, f'{emp.name}: invalid value — skipped.')
        messages.success(request, f'{saved} payroll record(s) saved.')
        return redirect(f'/employees/payroll/?session={session_id}&month={month}')

    # ── GET: Build table rows ───────────────────────────────────────────────
    rows = []
    days_in_month = None
    if current_session and selected_month:
        try:
            yr, mo = selected_month.split('-')
            _, days_in_month = monthrange(int(yr), int(mo))
            att_base = EmployeeAttendance.objects.filter(
                session=current_session, date__year=int(yr), date__month=int(mo)
            )
            entries = {
                e.employee_id: e
                for e in EmployeePayrollEntry.objects.filter(
                    session=current_session, month=selected_month
                )
            }
            # Show active employees + anyone with an existing entry for this session/month
            # (covers employees who have since left but had payroll in a previous year)
            from django.db.models import Q
            display_employees = Employee.objects.filter(
                Q(status='active') | Q(id__in=entries.keys())
            ).order_by('name')
            for emp in display_employees:
                emp_att  = att_base.filter(employee=emp)
                present  = emp_att.filter(attendance='present').count()
                halfday  = emp_att.filter(attendance='half-day').count()
                leave    = emp_att.filter(attendance='leave').count()
                entry = entries.get(emp.id)
                att_source = 'register'
                if present == 0 and halfday == 0 and leave == 0:
                    # No attendance register — try manual override, else full month leave
                    if entry and entry.manual_work_days is not None:
                        work_days = float(entry.manual_work_days)
                        leave     = int(entry.manual_leave_days or 0)
                        att_source = 'manual'
                    else:
                        work_days = 0
                        leave = days_in_month
                        att_source = 'none'
                else:
                    work_days = present + halfday * 0.5
                    att_source = 'register'
                monthly_salary = float(emp.base_salary_per_month or 0)
                total_tracked = work_days + leave
                register_salary = monthly_salary if (leave <= 2 and total_tracked >= days_in_month - 2) else min(round((monthly_salary / 30) * work_days, 2), monthly_salary)
                # Old dues only apply in April (first month of session)
                if mo == '04':
                    if entry:
                        old_dues_val = entry.old_dues
                    else:
                        old_dues_val = _calc_old_dues(emp, current_session, selected_month)
                else:
                    old_dues_val = 0
                rows.append({
                    'employee': emp,
                    'work_days': work_days,
                    'leave': leave,
                    'leaves_entitled': emp.leaves_entitled,
                    'register_salary': register_salary,
                    'payable_salary': entry.payable_salary if entry else '',
                    'old_dues': old_dues_val,
                    'other_amount': entry.other_amount if entry else 0,
                    'note': entry.note if entry else '',
                    'manual_work_days': entry.manual_work_days if entry else '',
                    'manual_leave_days': entry.manual_leave_days if entry else '',
                    'att_source': att_source,
                })
        except (ValueError, TypeError):
            pass

    # Determine if the selected month is April (old dues only apply in April)
    try:
        is_april = selected_month.split('-')[1] == '04' if selected_month else False
    except (IndexError, AttributeError):
        is_april = False

    # totals
    total_register   = sum(r['register_salary'] for r in rows)
    total_payable    = sum(float(r['payable_salary']) for r in rows if r['payable_salary'] not in ('', None))
    total_old_dues   = sum(float(r['old_dues'] or 0) for r in rows)
    total_other      = sum(float(r['other_amount'] or 0) for r in rows)

    context = {
        'sessions': sessions,
        'current_session': current_session,
        'selected_month': selected_month,
        'is_april': is_april,
        'rows': rows,
        'days_in_month': days_in_month,
        'total_register': total_register,
        'total_payable': total_payable,
        'total_old_dues': total_old_dues,
        'total_other': total_other,
    }
    return render(request, 'employees/employee_payroll_unified.html', context)


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

        # Preload old dues, payable salary and other amount from EmployeePayrollEntry for this session
        old_due_map = {}
        register_map = {}
        other_map = {}
        for entry in EmployeePayrollEntry.objects.filter(session=selected_session).values('employee_id', 'old_dues', 'payable_salary', 'other_amount'):
            eid = entry['employee_id']
            old_due_map[eid] = old_due_map.get(eid, 0) + float(entry['old_dues'] or 0)
            register_map[eid] = register_map.get(eid, 0) + float(entry['payable_salary'] or 0)
            other_map[eid]    = other_map.get(eid, 0)    + float(entry['other_amount'] or 0)

        # Preload all expenses for this session
        paid_map = {}
        for exp in Expense.objects.filter(session=selected_session, employee__isnull=False).values('employee_id', 'amount'):
            paid_map.setdefault(exp['employee_id'], 0)
            paid_map[exp['employee_id']] += float(exp['amount'])

        for emp in emp_qs:
            old_due       = old_due_map.get(emp.id, 0)
            salary_amount = register_map.get(emp.id, 0)
            other_amount  = other_map.get(emp.id, 0)
            paid          = paid_map.get(emp.id, 0)
            net_due = (old_due + salary_amount + other_amount) - paid
            rows.append({
                'employee': emp,
                'old_due': old_due,
                'salary_amount': salary_amount,
                'other_amount': other_amount,
                'paid': paid,
                'net_due': net_due,
            })
            total_old_due += old_due
            total_salary  += salary_amount
            total_paid    += paid

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
        'total_other': sum(r['other_amount'] for r in rows),
        'total_paid': total_paid,
        'total_net_due': total_net_due,
    })


def employee_salary_payment_record(request):
    """Salary Payment Record — one row per employee, summary (Total/Paid/Due) + monthly paid columns (Apr→Mar)."""
    from calendar import month_abbr

    sessions = Session.objects.all().order_by('-session')
    default_session = Session.objects.filter(status='current_session').first() or sessions.first()
    selected_session_id = request.GET.get('session', str(default_session.id) if default_session else '')
    selected_status = request.GET.get('status', '')

    selected_session = Session.objects.filter(pk=selected_session_id).first() if selected_session_id else None

    # Build month columns Apr→Mar based on session year
    month_cols = []
    if selected_session:
        try:
            start_year = int(selected_session.session.split('-')[0])
        except (ValueError, IndexError):
            start_year = 2023
        for m in range(4, 13):
            month_cols.append((month_abbr[m], f'{start_year}-{m:02d}'))
        for m in range(1, 4):
            month_cols.append((month_abbr[m], f'{start_year + 1}-{m:02d}'))

    rows = []
    col_totals = {mc: 0 for _, mc in month_cols}
    grand_total_salary = 0
    grand_paid_salary = 0

    if selected_session:
        emp_qs = Employee.objects.all().order_by('name')
        if selected_status:
            emp_qs = emp_qs.filter(status=selected_status)

        # Total salary per employee = sum(payable_salary) + sum(old_dues) from EmployeePayrollEntry
        total_salary_map = {}  # emp_id -> total_salary
        for entry in EmployeePayrollEntry.objects.filter(session=selected_session).values(
                'employee_id', 'payable_salary', 'old_dues'):
            eid = entry['employee_id']
            total_salary_map[eid] = (
                total_salary_map.get(eid, 0)
                + float(entry['payable_salary'] or 0)
                + float(entry['old_dues'] or 0)
            )

        # Monthly paid per employee: group Expense records by (employee_id, YYYY-MM)
        paid_monthly_map = {}  # (emp_id, 'YYYY-MM') -> paid amount
        for exp in Expense.objects.filter(
                session=selected_session, employee__isnull=False
        ).values('employee_id', 'date', 'amount'):
            d = exp['date']
            month_str = f'{d.year}-{d.month:02d}'
            key = (exp['employee_id'], month_str)
            paid_monthly_map[key] = paid_monthly_map.get(key, 0) + float(exp['amount'])

        for emp in emp_qs:
            total_salary = total_salary_map.get(emp.id, 0)
            monthly = []
            paid_salary = 0
            for label, month_str in month_cols:
                val = paid_monthly_map.get((emp.id, month_str), None)
                # treat 0-valued entries as None (blank)
                if val is not None and val > 0:
                    monthly.append(val)
                    paid_salary += val
                    col_totals[month_str] += val
                else:
                    monthly.append(None)
            due = total_salary - paid_salary
            rows.append({
                'employee': emp,
                'total_salary': total_salary,
                'paid_salary': paid_salary,
                'due': due,
                'monthly': monthly,
            })
            grand_total_salary += total_salary
            grand_paid_salary += paid_salary

    col_totals_list = [col_totals[mc] for _, mc in month_cols]
    grand_due = grand_total_salary - grand_paid_salary

    return render(request, 'employees/employee_salary_payment_record.html', {
        'sessions': sessions,
        'selected_session': selected_session,
        'selected_session_id': selected_session_id,
        'selected_status': selected_status,
        'status_choices': Employee.STATUS_CHOICES,
        'month_cols': month_cols,
        'rows': rows,
        'col_totals_list': col_totals_list,
        'grand_total_salary': grand_total_salary,
        'grand_paid_salary': grand_paid_salary,
        'grand_due': grand_due,
    })


def employee_salary_yearly(request):
    """Yearly salary grid — one row per employee, monthly columns (Apr→Mar) for a session."""
    from calendar import month_abbr

    sessions = Session.objects.all().order_by('-session')
    default_session = Session.objects.filter(status='current_session').first() or sessions.first()
    selected_session_id = request.GET.get('session', str(default_session.id) if default_session else '')
    selected_status = request.GET.get('status', '')

    selected_session = Session.objects.filter(pk=selected_session_id).first() if selected_session_id else None

    # Determine financial year months Apr→Mar based on session string e.g. "2023-2024"
    month_cols = []  # list of (label, YYYY-MM)
    if selected_session:
        try:
            start_year = int(selected_session.session.split('-')[0])
        except (ValueError, IndexError):
            start_year = 2023
        month_cols = []
        for m in range(4, 13):   # Apr–Dec of start_year
            month_cols.append((month_abbr[m], f'{start_year}-{m:02d}'))
        for m in range(1, 4):    # Jan–Mar of end_year
            month_cols.append((month_abbr[m], f'{start_year + 1}-{m:02d}'))

    rows = []
    col_totals = {mc: 0 for _, mc in month_cols}
    grand_old_dues = 0
    grand_total = 0

    if selected_session:
        emp_qs = Employee.objects.all().order_by('name')
        if selected_status:
            emp_qs = emp_qs.filter(status=selected_status)

        # Build payroll lookup: {(employee_id, month): payable_salary}
        payroll_qs = EmployeePayrollEntry.objects.filter(session=selected_session).values(
            'employee_id', 'month', 'payable_salary', 'old_dues'
        )
        salary_map = {}   # (emp_id, month) -> payable_salary
        old_due_map = {}  # emp_id -> old_dues (first month only)
        for entry in payroll_qs:
            eid = entry['employee_id']
            key = (eid, entry['month'])
            salary_map[key] = float(entry['payable_salary'] or 0)
            # old_dues: take the value from the earliest month entry
            existing = old_due_map.get(eid)
            if existing is None:
                old_due_map[eid] = float(entry['old_dues'] or 0)

        for emp in emp_qs:
            old_due = old_due_map.get(emp.id, 0)
            monthly = []
            row_total = 0
            for label, month_str in month_cols:
                val = salary_map.get((emp.id, month_str), None)
                monthly.append(val)
                if val:
                    row_total += val
                    col_totals[month_str] += val
            rows.append({
                'employee': emp,
                'old_due': old_due,
                'monthly': monthly,
                'row_total': row_total,
            })
            grand_old_dues += old_due
            grand_total += row_total

    col_totals_list = [col_totals[mc] for _, mc in month_cols]

    return render(request, 'employees/employee_salary_yearly.html', {
        'sessions': sessions,
        'selected_session': selected_session,
        'selected_session_id': selected_session_id,
        'selected_status': selected_status,
        'status_choices': Employee.STATUS_CHOICES,
        'month_cols': month_cols,
        'rows': rows,
        'col_totals_list': col_totals_list,
        'grand_old_dues': grand_old_dues,
        'grand_total': grand_total,
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
            for r in EmployeePayrollEntry.objects.filter(
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

        joining_date = selected_employee.joining_date  # may be None

        for (yr, mo) in fin_months:
            month_key = f"{yr}-{mo:02d}"
            # Basic pay is 0 for months before the employee joined
            import datetime
            month_start = datetime.date(yr, mo, 1)
            if joining_date and month_start < datetime.date(joining_date.year, joining_date.month, 1):
                month_basic_pay = 0
            else:
                month_basic_pay = float(base_salary)

            register = register_map.get(month_key)
            payable  = float(register.payable_salary)  if (register and register.payable_salary  is not None) else 0
            old_due  = float(register.old_dues)         if (register and register.old_dues         is not None) else 0
            other    = float(register.other_amount)     if (register and register.other_amount     is not None) else 0
            amount   = payable + old_due + other
            paid     = float(sum(e.amount for e in expense_by_month.get(month_key, [])))
            notes_parts = []
            if payable:  notes_parts.append(f'Salary: ₹{payable:,.2f}')
            if old_due:  notes_parts.append(f'Old Dues: ₹{old_due:,.2f}')
            if other:    notes_parts.append(f'Other: ₹{other:,.2f}')
            monthly_schedule.append({
                'year': yr,
                'month': cal_month_name[mo],
                'payment_type': 'Salary',
                'notes': ' | '.join(notes_parts),
                'basic_pay': month_basic_pay,
                'payable': payable,
                'old_due': old_due,
                'other': other,
                'amount': amount,
                'paid': paid,
                'net_due': amount - paid,
            })

        monthly_total = float(sum(r['amount'] for r in monthly_schedule))
        total_salary_due = monthly_total
        total_paid = float(sum(r['paid'] for r in monthly_schedule))

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


def _month_to_session_str(month_str):
    """Derive session string (e.g. '2024-2025') from a YYYY-MM month string.
    April–December belong to session {year}-{year+1}; Jan–March to {year-1}-{year}.
    """
    yr, mo = int(month_str[:4]), int(month_str[5:7])
    if mo >= 4:
        return f"{yr}-{yr + 1}"
    else:
        return f"{yr - 1}-{yr}"


def bulk_import_payroll(request):
    """Bulk import historical payroll (EmployeePayrollEntry) records from CSV."""
    from .forms import BulkImportPayrollForm

    import_result = None

    if request.method == 'POST':
        form = BulkImportPayrollForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            handle_duplicates = form.cleaned_data['handle_duplicates']
            dry_run = form.cleaned_data['dry_run']

            try:
                content = csv_file.read().decode('utf-8-sig')
                reader = csv.DictReader(content.splitlines())

                # Normalise headers
                if reader.fieldnames is None:
                    messages.error(request, 'CSV file is empty or has no header row.')
                    return render(request, 'employees/bulk_import_manual_salary_data.html',
                                  {'form': form, 'import_result': None})

                required = {'Emp_ID', 'Month', 'Payable_Salary'}
                headers = {h.strip() for h in reader.fieldnames}
                missing = required - headers
                if missing:
                    messages.error(request, f"Missing required column(s): {', '.join(sorted(missing))}")
                    return render(request, 'employees/bulk_import_manual_salary_data.html',
                                  {'form': form, 'import_result': None})

                # Pre-load lookups
                emp_map = {str(e.emp_no): e for e in Employee.objects.all()}
                session_map = {s.session: s for s in Session.objects.all()}

                valid_rows = []       # (row_num, parsed_data, employee, session)
                duplicate_rows = []   # same structure but entry already exists
                row_errors = []       # (row_num, message)

                for row_num, row in enumerate(reader, start=2):
                    emp_id_raw = row.get('Emp_ID', '').strip()
                    month_raw  = row.get('Month', '').strip()
                    payable_raw = row.get('Payable_Salary', '').strip()
                    old_dues_raw   = row.get('Old_Dues', '').strip() or '0'
                    other_raw      = row.get('Other_Amount', '').strip() or '0'
                    note_raw       = row.get('Note', '').strip()
                    manual_work_raw  = row.get('Manual_Work_Days', '').strip()
                    manual_leave_raw = row.get('Manual_Leave_Days', '').strip()

                    # Validate Emp_ID
                    emp = emp_map.get(emp_id_raw)
                    if not emp:
                        row_errors.append((row_num, f"Employee with Emp_ID '{emp_id_raw}' not found."))
                        continue

                    # Validate Month format
                    import re
                    if not re.match(r'^\d{4}-(0[1-9]|1[0-2])$', month_raw):
                        row_errors.append((row_num, f"Invalid Month '{month_raw}'. Use YYYY-MM (e.g. 2024-04)."))
                        continue

                    # Resolve session
                    session_str = _month_to_session_str(month_raw)
                    session = session_map.get(session_str)
                    if not session:
                        row_errors.append((row_num, f"Session '{session_str}' not found in the database."))
                        continue

                    # Validate numeric fields
                    try:
                        payable = float(payable_raw)
                        old_dues_val = float(old_dues_raw)
                        other_val = float(other_raw)
                        manual_work = float(manual_work_raw) if manual_work_raw else None
                        manual_leave = int(float(manual_leave_raw)) if manual_leave_raw else None
                    except ValueError:
                        row_errors.append((row_num, f"Non-numeric value in amount or days column."))
                        continue

                    parsed = {
                        'payable_salary': payable,
                        'old_dues': old_dues_val,
                        'other_amount': other_val,
                        'note': note_raw,
                        'manual_work_days': manual_work,
                        'manual_leave_days': manual_leave,
                        'month': month_raw,
                        'session_label': session_str,
                    }

                    exists = EmployeePayrollEntry.objects.filter(
                        session=session, employee=emp, month=month_raw
                    ).exists()

                    entry = (row_num, parsed, emp, session)
                    if exists:
                        duplicate_rows.append(entry)
                    else:
                        valid_rows.append(entry)

                for row_num, msg in row_errors:
                    messages.error(request, f"Row {row_num}: {msg}")

                created = updated = skipped = 0

                if not dry_run:
                    for row_num, parsed, emp, session in valid_rows:
                        try:
                            EmployeePayrollEntry.objects.create(
                                session=session, employee=emp,
                                month=parsed['month'],
                                payable_salary=parsed['payable_salary'],
                                old_dues=parsed['old_dues'],
                                other_amount=parsed['other_amount'],
                                note=parsed['note'],
                                manual_work_days=parsed['manual_work_days'],
                                manual_leave_days=parsed['manual_leave_days'],
                            )
                            created += 1
                        except Exception as e:
                            messages.error(request, f"Row {row_num}: Could not save — {e}")

                    for row_num, parsed, emp, session in duplicate_rows:
                        if handle_duplicates == 'skip':
                            skipped += 1
                        elif handle_duplicates == 'update':
                            try:
                                EmployeePayrollEntry.objects.filter(
                                    session=session, employee=emp, month=parsed['month']
                                ).update(
                                    payable_salary=parsed['payable_salary'],
                                    old_dues=parsed['old_dues'],
                                    other_amount=parsed['other_amount'],
                                    note=parsed['note'],
                                    manual_work_days=parsed['manual_work_days'],
                                    manual_leave_days=parsed['manual_leave_days'],
                                )
                                updated += 1
                            except Exception as e:
                                messages.error(request, f"Row {row_num}: Could not update — {e}")
                        else:  # error
                            messages.error(request, f"Row {row_num}: Duplicate entry for {emp.name} / {parsed['month']}.")

                    if created:
                        messages.success(request, f"Created {created} new payroll record(s).")
                    if updated:
                        messages.success(request, f"Updated {updated} existing record(s).")
                    if skipped:
                        messages.info(request, f"Skipped {skipped} duplicate(s).")

                    import_result = {
                        'dry_run': False,
                        'created': created,
                        'updated': updated,
                        'skipped': skipped,
                    }
                else:
                    # Dry-run preview
                    will_create = len(valid_rows)
                    will_update = len(duplicate_rows) if handle_duplicates == 'update' else 0
                    will_skip   = len(duplicate_rows) if handle_duplicates == 'skip'   else 0
                    will_error  = len(duplicate_rows) if handle_duplicates == 'error'  else 0
                    import_result = {
                        'dry_run': True,
                        'created': will_create,
                        'updated': will_update,
                        'skipped': will_skip,
                        'errors':  will_error,
                        'handle_duplicates': handle_duplicates,
                        'valid_rows': [
                            (rn, {**p, 'emp_name': emp.name, 'emp_id': emp.emp_no})
                            for rn, p, emp, _ in valid_rows
                        ],
                        'duplicate_rows': [
                            (rn, {**p, 'emp_name': emp.name, 'emp_id': emp.emp_no})
                            for rn, p, emp, _ in duplicate_rows
                        ],
                    }
                    messages.info(request, "Dry-run mode: No data was saved. Review the preview below.")

            except Exception as e:
                messages.error(request, f"Error processing file: {e}")
    else:
        form = BulkImportPayrollForm()

    return render(request, 'employees/bulk_import_manual_salary_data.html',
                  {'form': form, 'import_result': import_result})


def download_payroll_template(request):
    """Download a sample CSV template for payroll bulk import."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="payroll_import_template.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Emp_ID', 'Month', 'Payable_Salary',
        'Old_Dues', 'Other_Amount', 'Note',
        'Manual_Work_Days', 'Manual_Leave_Days',
    ])
    writer.writerow([1000, '2024-04', 8000, 0, 0, '', '', ''])
    writer.writerow([1002, '2024-05', 5000, 2500, 0, 'Advance adjusted', '', ''])
    writer.writerow([1004, '2024-06', 10000, 0, 500, 'Bonus', 22, 2])
    return response
