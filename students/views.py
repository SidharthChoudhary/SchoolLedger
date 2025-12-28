from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.urls import reverse
from datetime import date
from dailyLedger.models import Session
from .models import (
    Student,
    StudentAccount,
    Class,
    FeesAccount,
    SessionClassStudentMap,
    StudentAttendance,
)
from .forms import StudentForm, ClassForm, FeesAccountForm


def add_student(request):
    """Redirect to view_students for add/edit functionality"""
    return redirect('view_students')


def confirm_fee_account_link(request):
    """Confirm linking fee account to student"""
    pending_account = request.session.get('pending_fee_account')
    
    if not pending_account:
        return redirect('add_student')
    
    if request.method == 'POST':
        link_account = request.POST.get('link_account') == 'yes'
        
        student = get_object_or_404(Student, pk=pending_account['student_id'])
        fees_account = get_object_or_404(FeesAccount, pk=pending_account['fees_account_id'])
        
        if link_account:
            # Link the fee account to the student
            student.fees_account = fees_account
            student.save()
            messages.success(request, f'Fee account {pending_account["account_id"]} linked to student successfully!')
            redirect_url = 'view_students'
        else:
            messages.info(request, f'Fee account {pending_account["account_id"]} created but not linked to student.')
            redirect_url = 'add_student'
        
        # Clear session
        del request.session['pending_fee_account']
        return redirect(redirect_url)
    
    student = get_object_or_404(Student, pk=pending_account['student_id'])
    
    return render(request, 'students/confirm_fee_account.html', {
        'student': student,
        'account_id': pending_account['account_id'],
        'account_name': pending_account['account_name']
    })

def confirm_student_addition(request):
    """Confirm student addition without primary account holder"""
    student_success = request.session.get('student_success')
    
    if not student_success:
        return redirect('add_student')
    
    if request.method == 'POST':
        # Clear session and redirect to view students
        del request.session['student_success']
        return redirect('view_students')
    
    return render(request, 'students/confirm_student_addition.html', {
        'student_name': student_success['student_name'],
        'primary_account_holder': student_success['primary_account_holder']
    })

def view_students(request):
    """View all students in a table and add/edit students on same page"""
    editing_student = None
    form = None
    
    # Check if editing a student
    edit_id = request.GET.get('edit')
    if edit_id:
        editing_student = get_object_or_404(Student, pk=edit_id)
    
    if request.method == 'POST':
        if edit_id:
            # Editing existing student
            form = StudentForm(request.POST, request.FILES, instance=editing_student)
        else:
            # Adding new student
            form = StudentForm(request.POST, request.FILES)
        
        if form.is_valid():
            student = form.save(commit=False)
            
            # Check if Primary Account Holder is checked
            if student.primary_account_holder:
                # Create a new FeesAccount automatically
                last_account = FeesAccount.objects.all().order_by('id').last()
                if last_account:
                    last_id = int(last_account.account_id)
                    next_id = last_id + 1
                else:
                    next_id = 1
                
                account_id = str(next_id).zfill(3)
                account_name = f"{account_id}-{student.last_name} {student.first_name}-{student.srn}"
                
                # Create the FeesAccount
                fees_account = FeesAccount.objects.create(
                    account_id=account_id,
                    name=account_name,
                    account_open=date.today(),
                    account_status='open'
                )
                
                # Save student without linking yet
                student.save()
                
                # Store fee account info in session for confirmation
                request.session['pending_fee_account'] = {
                    'account_id': account_id,
                    'account_name': account_name,
                    'student_id': student.id,
                    'fees_account_id': fees_account.id
                }
                
                return redirect('confirm_fee_account_link')
            else:
                student.save()
                messages.success(request, f'Student {"updated" if edit_id else "added"} successfully!')
                return redirect('view_students')
    else:
        if edit_id:
            form = StudentForm(instance=editing_student)
        else:
            form = StudentForm()
    
    students = Student.objects.all().order_by('student_class', 'first_name')
    return render(request, 'students/view_students.html', {
        'students': students,
        'form': form,
        'editing_student': editing_student
    })


def student_details(request, pk):
    """View student details in read-only format"""
    student = get_object_or_404(Student, pk=pk)
    return render(request, 'students/student_details.html', {'student': student})


def edit_student(request, pk):
    """Redirect to view_students for add/edit functionality"""
    return redirect(f'{reverse("view_students")}?edit={pk}')


def delete_student(request, pk):
    """Delete a student"""
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        student.delete()
        messages.success(request, 'Student deleted successfully!')
        return redirect('view_students')
    
    return render(request, 'students/delete_student.html', {'student': student})


def select_student_for_account(request):
    """Select a student to view their account"""
    students = Student.objects.all().order_by('student_class', 'first_name')
    return render(request, 'students/select_student_account.html', {'students': students})


def student_account_detail(request, student_id):
    """View student account with all fees"""
    student = get_object_or_404(Student, pk=student_id)
    accounts = StudentAccount.objects.filter(student=student).order_by('-session')
    
    return render(request, 'students/student_account_detail.html', {
        'student': student,
        'accounts': accounts
    })


def student_year_view(request):
    """View all classes with their ages"""
    all_classes = Class.objects.all().order_by('age')
    
    return render(request, 'students/year_view.html', {
        'all_classes': all_classes
    })


def view_classes(request):
    """View, add, and edit classes on a single page"""
    edit_id = request.GET.get("edit")
    editing_class = Class.objects.filter(pk=edit_id).first() if edit_id else None

    if request.method == "POST":
        class_id = request.POST.get("class_id")
        if class_id:
            form = ClassForm(request.POST, instance=get_object_or_404(Class, pk=class_id))
        else:
            form = ClassForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("view_classes")
    else:
        form = ClassForm(instance=editing_class) if editing_class else ClassForm()

    classes = Class.objects.all().order_by('age')

    return render(
        request,
        'students/view_classes.html',
        {
            'form': form,
            'classes': classes,
            'editing_class': editing_class,
        }
    )


def add_class(request):
    """Redirect to view_classes for adding new classes"""
    return redirect('view_classes')


def edit_class(request, pk):
    """Redirect to view_classes with edit parameter"""
    return redirect(f'/students/classes/?edit={pk}')


def delete_class(request, pk):
    """Delete a class"""
    school_class = get_object_or_404(Class, pk=pk)
    if request.method == 'POST':
        school_class.delete()
        return redirect('view_classes')
    
    return render(request, 'students/delete_class.html', {'class': school_class})




def validate_account_names():
    """Validate and update account names based on primary account holders"""
    # Get all fee accounts
    fee_accounts = FeesAccount.objects.all()
    updated_count = 0
    
    for account in fee_accounts:
        # Find students who are primary account holders linked to this account
        primary_students = Student.objects.filter(
            fees_account=account,
            primary_account_holder=True
        )
        
        # If there's a primary account holder, update the account name
        if primary_students.exists():
            # Take the first primary account holder
            student = primary_students.first()
            
            # Generate account name: AccID-LastName FirstName-SRN-RegisterNumber
            # Note: RegisterNumber could be register_page field
            new_account_name = f"{account.account_id}-{student.last_name} {student.first_name}-{student.srn}-{account.register_page or ''}"
            new_account_name = new_account_name.rstrip('-')  # Remove trailing dash if no register_page
            
            account.name = new_account_name
            account.save()
            updated_count += 1
    
    return updated_count


def view_fees_accounts(request):
    """View, add, and edit fees accounts on a single page"""
    
    # Handle validate account names action
    if request.method == "POST" and request.POST.get("action") == "validate":
        updated_count = validate_account_names()
        if updated_count > 0:
            messages.success(request, f'Account names have been validated and updated successfully! ({updated_count} account(s) updated)')
        else:
            messages.warning(request, 'No primary account holders found. No accounts were updated.')
        return redirect("/students/fees-account/?validation_complete=true")
    
    edit_id = request.GET.get("edit")
    editing_account = FeesAccount.objects.filter(pk=edit_id).first() if edit_id else None

    if request.method == "POST":
        account_id = request.POST.get("account_id_hidden")
        if account_id:
            form = FeesAccountForm(request.POST, instance=get_object_or_404(FeesAccount, pk=account_id))
        else:
            form = FeesAccountForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("view_fees_accounts")
    else:
        form = FeesAccountForm(instance=editing_account) if editing_account else FeesAccountForm()

    accounts = FeesAccount.objects.all().order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        accounts = accounts.filter(account_status=status_filter)
    
    # Filter by account ID
    account_id_filter = request.GET.get('account_id', '')
    if account_id_filter:
        accounts = accounts.filter(account_id__icontains=account_id_filter)
    
    # Filter by name
    name_filter = request.GET.get('name', '')
    if name_filter:
        accounts = accounts.filter(name__icontains=name_filter)
    
    # Filter by register page
    register_page_filter = request.GET.get('register_page', '')
    if register_page_filter:
        accounts = accounts.filter(register_page__icontains=register_page_filter)
    
    # Filter by open date
    open_date_filter = request.GET.get('open_date', '')
    if open_date_filter:
        accounts = accounts.filter(account_open=open_date_filter)
    
    # Filter by close date
    close_date_filter = request.GET.get('close_date', '')
    if close_date_filter:
        accounts = accounts.filter(account_close=close_date_filter)
    
    context = {
        'form': form,
        'accounts': accounts,
        'editing_account': editing_account,
        'status_filter': status_filter,
        'account_id_filter': account_id_filter,
        'name_filter': name_filter,
        'register_page_filter': register_page_filter,
        'open_date_filter': open_date_filter,
        'close_date_filter': close_date_filter,
    }
    return render(request, 'students/view_fees_accounts.html', context)


def add_fees_account(request):
    """Redirect to view_fees_accounts for adding new fees accounts"""
    return redirect('view_fees_accounts')


def edit_fees_account(request, pk):
    """Redirect to view_fees_accounts with edit parameter"""
    return redirect(f'/students/fees-account/?edit={pk}')


def delete_fees_account(request, pk):
    """Delete a fees account"""
    account = get_object_or_404(FeesAccount, pk=pk)
    if request.method == 'POST':
        account.delete()
        return redirect('view_fees_accounts')
    
    return render(request, 'students/delete_fees_account.html', {'account': account})


def link_fee_account(request):
    """Link fee account to student by Student Name or Account Register Page Number"""
    if request.method == 'POST':
        action = request.POST.get('action')
        
        # Link by Student Name
        if action == 'link_by_student':
            student_id = request.POST.get('student_id')
            account_id = request.POST.get('account_id')
            
            if student_id and account_id:
                student = get_object_or_404(Student, pk=student_id)
                account = get_object_or_404(FeesAccount, pk=account_id)
                student.fees_account = account
                student.save()
                messages.success(request, f'Fee account {account.account_id} linked to {student.first_name} {student.last_name} successfully!')
                return redirect('link_fee_account')
        
        # Link by Account Register Page Number
        elif action == 'link_by_register_page':
            register_page = request.POST.get('register_page')
            student_id = request.POST.get('student_id_register')
            
            if register_page and student_id:
                account = get_object_or_404(FeesAccount, register_page=register_page)
                student = get_object_or_404(Student, pk=student_id)
                student.fees_account = account
                student.save()
                messages.success(request, f'Fee account {account.account_id} linked to {student.first_name} {student.last_name} successfully!')
                return redirect('link_fee_account')
        
        # Update account from Panel 3 (populate Panel 1)
        elif action == 'update_from_panel3':
            student_id = request.POST.get('student_id')
            if student_id:
                return redirect(f'/students/link-fee-account/?student_id={student_id}')
    
    # Get sessions and classes for dropdowns
    from dailyLedger.models import Session
    sessions = Session.objects.all()
    classes = Class.objects.all().order_by('age')
    
    # Get open accounts
    open_accounts = FeesAccount.objects.filter(account_status='open')
    
    # Get all students for register page panel
    students = Student.objects.all()
    
    # Get students with no fee account linked
    students_no_account = Student.objects.filter(fees_account__isnull=True)
    
    # Apply filters for Panel 3
    session_filter = request.GET.get('session_filter')
    class_filter = request.GET.get('class_filter')
    student_name_filter = request.GET.get('student_name_filter')
    
    if session_filter:
        students_no_account = students_no_account.filter(session_id=session_filter)
    if class_filter:
        students_no_account = students_no_account.filter(student_class_id=class_filter)
    if student_name_filter:
        students_no_account = students_no_account.filter(
            first_name__icontains=student_name_filter) | students_no_account.filter(last_name__icontains=student_name_filter)
    
    # Panel 4 - All students with their accounts
    all_students = Student.objects.all().select_related('session', 'student_class', 'fees_account')
    
    # Apply filters for Panel 4
    session_filter_p4 = request.GET.get('session_filter_p4', '').strip()
    class_filter_p4 = request.GET.get('class_filter_p4', '').strip()
    student_name_filter_p4 = request.GET.get('student_name_filter_p4', '').strip()
    account_name_filter_p4 = request.GET.get('account_name_filter_p4', '').strip()
    register_page_filter_p4 = request.GET.get('register_page_filter_p4', '').strip()
    
    # Build filtered queryset for display
    filtered_students = all_students
    
    # Apply each filter only if it has a value
    if session_filter_p4:
        try:
            filtered_students = filtered_students.filter(session_id=int(session_filter_p4))
        except (ValueError, TypeError):
            pass
    
    if class_filter_p4:
        try:
            filtered_students = filtered_students.filter(student_class_id=int(class_filter_p4))
        except (ValueError, TypeError):
            pass
    
    if student_name_filter_p4 and student_name_filter_p4 != 'None':
        try:
            filtered_students = filtered_students.filter(id=int(student_name_filter_p4))
        except (ValueError, TypeError):
            pass
    
    if account_name_filter_p4 and account_name_filter_p4 != 'None':
        try:
            filtered_students = filtered_students.filter(fees_account_id=int(account_name_filter_p4))
        except (ValueError, TypeError):
            pass
    
    if register_page_filter_p4 and register_page_filter_p4 != 'None':
        filtered_students = filtered_students.filter(fees_account__register_page=register_page_filter_p4)
    
    # Get the student_id from query params to pre-select in Panel 1
    pre_selected_student_id = request.GET.get('student_id')
    
    context = {
        'sessions': sessions,
        'classes': classes,
        'open_accounts': open_accounts,
        'students': students,
        'students_no_account': students_no_account,
        'all_students': all_students,
        'filtered_students': filtered_students,
        'session_filter': session_filter,
        'class_filter': class_filter,
        'student_name_filter': student_name_filter,
        'session_filter_p4': session_filter_p4,
        'class_filter_p4': class_filter_p4,
        'student_name_filter_p4': student_name_filter_p4,
        'account_name_filter_p4': account_name_filter_p4,
        'register_page_filter_p4': register_page_filter_p4,
        'pre_selected_student_id': pre_selected_student_id,
    }
    
    return render(request, 'students/link_fee_account.html', context)


def student_attendance_classes(request):
    """Render class buttons so admin can pick a class"""
    classes = Class.objects.all().order_by('age')
    sessions = Session.objects.all().order_by('-session')
    current_session = Session.objects.filter(status='current_session').first()
    today = date.today()

    # Check which classes have submitted attendance for today
    classes_with_status = []
    for cls in classes:
        # Check if any attendance record exists for this class on today's date with current session
        has_submitted = StudentAttendance.objects.filter(
            student_class=cls,
            session=current_session,
            date=today
        ).exists()
        classes_with_status.append({
            'class': cls,
            'has_submitted': has_submitted
        })

    return render(request, 'students/student_attendance_classes.html', {
        'classes_with_status': classes_with_status,
        'sessions': sessions,
        'current_session': current_session,
    })


def student_attendance_register(request, class_id):
    """Mark attendance for students in a specific class"""
    selected_class = get_object_or_404(Class, pk=class_id)
    classes = Class.objects.all().order_by('age')
    sessions = Session.objects.all().order_by('-session')
    current_session = Session.objects.filter(status='current_session').first()

    selected_session = current_session or (sessions.first() if sessions.exists() else None)
    selected_session_id = request.GET.get('session')
    if selected_session_id:
        selected_session = get_object_or_404(Session, pk=selected_session_id)

    selected_date_str = request.GET.get('date') or date.today().isoformat()
    try:
        selected_date = date.fromisoformat(selected_date_str)
    except (ValueError, TypeError):
        selected_date = date.today()
        selected_date_str = selected_date.isoformat()

    students_in_class = Student.objects.filter(student_class=selected_class).select_related('student_class').order_by('first_name', 'last_name')

    if request.method == 'POST':
        session_id = request.POST.get('session')
        attendance_session = Session.objects.filter(pk=session_id).first() if session_id else selected_session

        if not attendance_session:
            messages.error(request, 'Please select a session before saving attendance.')
            return redirect('student_attendance_register', class_id=class_id)

        attendance_date_str = request.POST.get('date') or selected_date_str
        try:
            attendance_date = date.fromisoformat(attendance_date_str)
        except (ValueError, TypeError):
            attendance_date = selected_date

        for student in students_in_class:
            attendance_value = request.POST.get(f'attendance_{student.id}')
            if attendance_value:
                StudentAttendance.objects.update_or_create(
                    session=attendance_session,
                    student_class=selected_class,
                    student=student,
                    date=attendance_date,
                    defaults={'attendance': attendance_value}
                )

        class_label = selected_class.class_code or selected_class.class_name
        messages.success(request, f'Attendance saved for {class_label} on {attendance_date.strftime("%d-%m-%Y")}')
        return redirect('student_attendance_register', class_id=class_id)

    attendance_records = {}
    if selected_session:
        records = StudentAttendance.objects.filter(
            session=selected_session,
            date=selected_date,
            student_class=selected_class
        ).values('student_id', 'attendance')
        attendance_records = {r['student_id']: r['attendance'] for r in records}

    return render(request, 'students/student_attendance_register.html', {
        'classes': classes,
        'selected_class': selected_class,
        'students': students_in_class,
        'sessions': sessions,
        'current_session': current_session,
        'selected_session': selected_session,
        'selected_date': selected_date,
        'selected_date_str': selected_date_str,
        'attendance_records': attendance_records,
    })


def student_attendance_records(request):
    """Show all stored student attendance entries with attendance percentages"""
    records = StudentAttendance.objects.select_related('session', 'student_class', 'student').order_by('-date', 'student_class__age')
    
    # Group records by session, class, and date, then calculate attendance percentage
    grouped_records = {}
    for record in records:
        key = (record.session.id, record.student_class.id, record.date)
        if key not in grouped_records:
            grouped_records[key] = {
                'session': record.session,
                'student_class': record.student_class,
                'date': record.date,
                'total_students': 0,
                'present_count': 0,
                'percentage': 0
            }
        
        grouped_records[key]['total_students'] += 1
        if record.attendance == 'present':
            grouped_records[key]['present_count'] += 1
    
    # Calculate percentages
    for record in grouped_records.values():
        if record['total_students'] > 0:
            record['percentage'] = round((record['present_count'] / record['total_students']) * 100)
    
    # Sort by date descending
    sorted_records = sorted(grouped_records.values(), key=lambda x: x['date'], reverse=True)
    
    return render(request, 'students/student_attendance_records.html', {
        'records': sorted_records,
    })


def manage_session_class_student_map(request):
    """Manage session-class-student mapping with promotion functionality"""
    from .models import SessionClassStudentMap
    from dailyLedger.models import Session
    
    # Panel 1: Admit student to class
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'admit_student':
            session_id = request.POST.get('session')
            class_id = request.POST.get('class')
            student_id = request.POST.get('student')
            
            if session_id and class_id and student_id:
                try:
                    session = Session.objects.get(id=session_id)
                    student_class = Class.objects.get(id=class_id)
                    student = Student.objects.get(id=student_id)
                    
                    # Create or get the mapping
                    map_obj, created = SessionClassStudentMap.objects.get_or_create(
                        session=session,
                        student_class=student_class,
                        student=student,
                        defaults={'srn': student.srn}
                    )
                    
                    if created:
                        messages.success(request, f"{student.first_name} {student.last_name} admitted to {student_class.class_code} in {session.session}")
                    else:
                        messages.warning(request, f"{student.first_name} {student.last_name} is already in {student_class.class_code} for {session.session}")
                    
                except Exception as e:
                    messages.error(request, f"Error: {str(e)}")
    
    # Get data for dropdowns
    from dailyLedger.models import Session
    all_sessions = Session.objects.all().order_by('-id')
    active_sessions = Session.objects.filter(status='current_session').order_by('-id')
    new_sessions = Session.objects.filter(status='next_session').order_by('-id')
    classes = Class.objects.all().order_by('age')
    
    # Get students NOT mapped to any session/class
    mapped_student_ids = SessionClassStudentMap.objects.values_list('student_id', flat=True).distinct()
    unmapped_students = Student.objects.exclude(id__in=mapped_student_ids).order_by('first_name', 'last_name')
    
    # Get current session for default selection
    current_session = Session.objects.filter(status='current_session').first()
    
    # Get existing mappings for display
    existing_mappings = SessionClassStudentMap.objects.all().select_related(
        'session', 'student_class', 'student'
    ).order_by('-created_at')
    
    context = {
        'all_sessions': all_sessions,
        'active_sessions': active_sessions,
        'new_sessions': new_sessions,
        'classes': classes,
        'students': unmapped_students,
        'existing_mappings': existing_mappings,
        'current_session': current_session,
    }
    
    return render(request, 'students/manage_session_class_student_map.html', context)


def get_next_class(request, class_id):
    """API endpoint to get the next class for promotion"""
    try:
        current_class = Class.objects.get(id=class_id)
        
        # Find next class by ID
        next_class = Class.objects.filter(id__gt=current_class.id).order_by('id').first()
        if not next_class:
            # If no next class by ID, find by age
            next_class = Class.objects.filter(age__gt=current_class.age).order_by('age').first()
        
        if next_class:
            return JsonResponse({
                'next_class': {
                    'id': next_class.id,
                    'class_code': next_class.class_code,
                    'age': next_class.age
                }
            })
        else:
            return JsonResponse({'next_class': None})
    except:
        return JsonResponse({'error': 'Class not found'}, status=404)


def delete_session_class_student_map(request, mapping_id):
    """Delete a session-class-student mapping"""
    mapping = get_object_or_404(SessionClassStudentMap, id=mapping_id)
    if request.method == 'POST':
        mapping.delete()
        messages.success(request, 'Mapping deleted successfully')
        return redirect('manage_session_class_student_map')
    return render(request, 'students/delete_session_class_student_map.html', {'mapping': mapping})


def promote_session_page(request):
    """Promote students from current session to new session"""
    from dailyLedger.models import Session
    
    # Handle POST request for promotion
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'promote_session':
            current_session_id = request.POST.get('current_session')
            new_session_id = request.POST.get('new_session')
            current_class_id = request.POST.get('current_class')
            new_class_id = request.POST.get('new_class')
            
            if current_session_id and new_session_id and current_class_id and new_class_id:
                try:
                    current_session = Session.objects.get(id=current_session_id)
                    new_session = Session.objects.get(id=new_session_id)
                    current_class = Class.objects.get(id=current_class_id)
                    new_class = Class.objects.get(id=new_class_id)
                    
                    # Delete existing mappings for new session and class to avoid duplicates
                    SessionClassStudentMap.objects.filter(
                        session=new_session,
                        student_class=new_class
                    ).delete()
                    
                    # Get all mappings from current session and class
                    current_mappings = SessionClassStudentMap.objects.filter(
                        session=current_session,
                        student_class=current_class
                    )
                    
                    promoted_count = 0
                    for mapping in current_mappings:
                        # Create new mapping for new session and class
                        SessionClassStudentMap.objects.get_or_create(
                            session=new_session,
                            student_class=new_class,
                            student=mapping.student,
                            defaults={
                                'srn': mapping.student.srn,
                                'promoted_date': timezone.now()
                            }
                        )
                        promoted_count += 1
                    
                    messages.success(request, f"Successfully promoted {promoted_count} students from {current_class.class_code} ({current_session.session}) to {new_class.class_code} ({new_session.session})")
                    
                except Exception as e:
                    messages.error(request, f"Error during promotion: {str(e)}")
    
    # Get data for dropdowns
    active_sessions = Session.objects.filter(status='current_session').order_by('-id')
    new_sessions = Session.objects.filter(status='next_session').order_by('-id')
    classes = Class.objects.all().order_by('age')
    
    context = {
        'active_sessions': active_sessions,
        'new_sessions': new_sessions,
        'classes': classes,
    }
    
    return render(request, 'students/promote_session.html', context)
