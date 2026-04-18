from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.http import HttpResponse
from django.urls import reverse
from django.db.models import Q, Count, Sum
from datetime import date
from decimal import Decimal
import csv
from django.views.decorators.cache import never_cache
from dailyLedger.models import Session, FeesStructure, Income
from .models import (
    Student,
    StudentAccount,
    Class,
    FeesAccount,
    FeesAccountAgreement,
    SessionClassStudentMap,
    StudentAttendance,
)
from .forms import StudentForm, ClassForm, FeesAccountForm, FeesAccountAgreementForm


@never_cache
def add_student(request):
    """Redirect to view_students for add/edit functionality"""
    return redirect(f"{reverse('view_students')}?mode=add#student-form")


def bulk_import_students(request):
    from .forms import BulkImportStudentForm
    from .utils import parse_csv_students, import_students

    import_result = None

    if request.method == 'POST':
        form = BulkImportStudentForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            handle_duplicates = form.cleaned_data['handle_duplicates']
            dry_run = form.cleaned_data['dry_run']

            try:
                csv_content = csv_file.read().decode('utf-8')
                parse_result = parse_csv_students(csv_content, handle_duplicates)

                if parse_result['errors']:
                    for row_num, msg in parse_result['errors']:
                        messages.error(request, f'Row {row_num}: {msg}')

                if parse_result['warnings']:
                    for row_num, msg in parse_result['warnings']:
                        messages.warning(request, f'Row {row_num}: {msg}')

                if parse_result['valid_rows'] or parse_result['duplicate_rows']:
                    if dry_run:
                        import_result = {
                            'created': len(parse_result['valid_rows']),
                            'updated': len(parse_result['duplicate_rows']) if handle_duplicates == 'update' else 0,
                            'skipped': len(parse_result['duplicate_rows']) if handle_duplicates == 'skip' else 0,
                            'dry_run': True,
                            'valid_rows': parse_result['valid_rows'],
                            'duplicate_rows': parse_result['duplicate_rows'],
                            'handle_duplicates': handle_duplicates,
                        }
                        messages.info(request, "Dry run mode: no records were written. Uncheck 'Dry Run' to import.")
                    else:
                        import_result = import_students(
                            parse_result['valid_rows'],
                            parse_result['duplicate_rows'],
                            handle_duplicates,
                        )
                        if import_result['created']:
                            messages.success(request, f"Created {import_result['created']} student(s)")
                        if import_result['updated']:
                            messages.success(request, f"Updated {import_result['updated']} student(s)")
                        if import_result['skipped']:
                            messages.info(request, f"Skipped {import_result['skipped']} duplicate student(s)")
                        if import_result.get('accounts_created'):
                            messages.success(
                                request,
                                f"Auto-created and linked {import_result['accounts_created']} fee account(s) for primary account holders"
                            )
                        if import_result['errors']:
                            for row_num, msg in import_result['errors']:
                                messages.error(request, f'Row {row_num}: {msg}')
                else:
                    messages.error(request, 'No valid records to import')

            except Exception as exc:
                messages.error(request, f'Error processing file: {exc}')
    else:
        form = BulkImportStudentForm()

    return render(
        request,
        'students/bulk_import_students.html',
        {
            'form': form,
            'import_result': import_result,
        },
    )


def download_students_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="students_template.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'First_Name', 'Last_Name', 'Gender', 'Fathers_Name', 'Mothers_Name',
        'Class_Code', 'Class_Name', 'Session', 'SRN', 'NIC_Student_ID',
        'Date_of_Birth', 'Admission_Date', 'Transport_Method', 'RTE', 'Primary_Account_Holder',
        'Fathers_Phone', 'Mothers_Phone', 'Gardians_Name', 'Gardians_Phone',
        'Previous_School', 'Medical_Conditions', 'Dietary_Restrictions'
    ])
    writer.writerow([
        'Aarav', 'Sharma', 'male', 'Rajesh Sharma', 'Sunita Sharma',
        '5', 'Class 5', '2025-2026', 'SRN-1001', 'NIC-2025-0001',
        '2015-06-14', '2025-04-01', 'yes', 'no', 'no',
        '9876543210', '9876543211', '', '',
        'ABC Public School', '', ''
    ])
    writer.writerow([
        'Anaya', 'Verma', 'female', 'Manoj Verma', 'Priya Verma',
        '6', 'Class 6', '2025-2026', 'SRN-1002', 'NIC-2025-0002',
        '2014-09-03', '2025-04-01', 'no', 'yes', 'no',
        '9876543220', '9876543221', '', '',
        '', 'Asthma', 'No peanuts'
    ])

    return response


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
    page_mode = request.GET.get('mode', 'list')
    selected_session = request.GET.get('session', '')
    selected_class = request.GET.get('student_class', '')
    selected_fee_account = request.GET.get('fee_account', '')
    filter_name = request.GET.get('name', '').strip()
    filter_srn = request.GET.get('srn', '').strip()
    
    # Check if editing a student
    edit_id = request.GET.get('edit')
    if edit_id:
        editing_student = get_object_or_404(Student, pk=edit_id)
        page_mode = 'add'
    
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
    
    students = Student.objects.select_related('session', 'student_class', 'fees_account').all()

    if page_mode == 'list':
        if selected_session:
            students = students.filter(session_id=selected_session)
        if selected_class:
            students = students.filter(student_class_id=selected_class)
        if filter_name:
            students = students.filter(
                Q(first_name__icontains=filter_name)
                | Q(last_name__icontains=filter_name)
                | Q(fathers_name__icontains=filter_name)
            )
        if filter_srn:
            students = students.filter(srn__icontains=filter_srn)
        if selected_fee_account:
            if selected_fee_account == 'unlinked':
                students = students.filter(fees_account__isnull=True)
            else:
                students = students.filter(fees_account_id=selected_fee_account)

    students = students.order_by('student_class', 'first_name', 'last_name')
    sessions = Session.objects.all().order_by('session')
    classes = Class.objects.all().order_by('age', 'class_name')
    fees_accounts = FeesAccount.objects.all().order_by('account_id', 'name')

    return render(request, 'students/view_students.html', {
        'students': students,
        'sessions': sessions,
        'classes': classes,
        'fees_accounts': fees_accounts,
        'form': form,
        'editing_student': editing_student,
        'page_mode': page_mode,
        'selected_session': selected_session,
        'selected_class': selected_class,
        'selected_fee_account': selected_fee_account,
        'filter_name': filter_name,
        'filter_srn': filter_srn,
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

    selected_session = request.GET.get('session', '')
    selected_class = request.GET.get('student_class', '')
    filter_name = request.GET.get('name', '').strip()
    filter_srn = request.GET.get('srn', '').strip()

    if selected_session:
        students = students.filter(session_id=selected_session)
    if selected_class:
        students = students.filter(student_class_id=selected_class)
    if filter_name:
        students = students.filter(
            Q(first_name__icontains=filter_name)
            | Q(last_name__icontains=filter_name)
            | Q(fathers_name__icontains=filter_name)
        )
    if filter_srn:
        students = students.filter(srn__icontains=filter_srn)

    sessions = Session.objects.all().order_by('session')
    classes = Class.objects.all().order_by('age', 'class_name')

    return render(request, 'students/select_student_account.html', {
        'students': students,
        'sessions': sessions,
        'classes': classes,
        'selected_session': selected_session,
        'selected_class': selected_class,
        'filter_name': filter_name,
        'filter_srn': filter_srn,
        'page_title': 'Student Account',
        'card_title': 'Select a Student',
        'target_url_name': 'student_account_detail',
    })


def select_fee_account_for_agreement(request):
    """Select a fees account to open account-level agreed fees"""
    accounts = FeesAccount.objects.annotate(student_count=Count('students')).order_by('account_id')

    account_id_filter = request.GET.get('account_id', '').strip()
    name_filter = request.GET.get('name', '').strip()

    if account_id_filter:
        accounts = accounts.filter(account_id__icontains=account_id_filter)
    if name_filter:
        accounts = accounts.filter(name__icontains=name_filter)

    return render(request, 'students/select_fee_account_agreement.html', {
        'accounts': accounts,
        'account_id_filter': account_id_filter,
        'name_filter': name_filter,
    })


def student_account_detail(request, student_id):
    """View student account with all fees"""
    student = get_object_or_404(Student, pk=student_id)
    accounts = StudentAccount.objects.filter(student=student).order_by('-session')
    
    return render(request, 'students/student_account_detail.html', {
        'student': student,
        'accounts': accounts
    })


def fee_account_agreement(request, account_id):
    """Compare summed standard fees for all students in an account vs agreed account-level fees."""
    fees_account = FeesAccount.objects.filter(pk=account_id).first()
    if not fees_account:
        # Backward-compatibility: old links may still pass student_id instead of account_id.
        student = Student.objects.select_related('fees_account').filter(pk=account_id).first()
        if student and student.fees_account_id:
            messages.info(request, 'Opened linked fees account for selected student.')
            return redirect('fee_account_agreement', account_id=student.fees_account_id)

        messages.error(request, 'Fees account not found. Please select a valid fees account.')
        return redirect('select_fee_account_agreement')

    sessions = Session.objects.all().order_by('-session')

    selected_session_id = (request.POST.get('session') or request.GET.get('session') or '').strip()
    selected_session = Session.objects.filter(id=selected_session_id).first() if selected_session_id else None

    linked_students = Student.objects.filter(fees_account=fees_account).select_related('student_class', 'session').order_by('student_class__age', 'first_name')
    if selected_session:
        linked_students = linked_students.filter(session=selected_session)

    fee_heads = [
        ('tuition_fees', 'fee_tuition'),
        ('tc_fees', 'fee_tc'),
        ('admission_fees', 'fee_admission'),
        ('book_set', 'book_set'),
        ('book_diary', 'book_diary'),
        ('book_other', 'book_other'),
        ('uniform_shirt', 'uniform_shirt'),
        ('uniform_pant', 'uniform_pant'),
        ('uniform_sweater', 'uniform_sweater'),
        ('uniform_hoody', 'uniform_hoody'),
        ('uniform_t_shirt', 'uniform_t_shirt'),
        ('uniform_tie', 'uniform_tie'),
        ('uniform_belt', 'uniform_belt'),
        ('uniform_id_card', 'uniform_id_card'),
    ]
    standard_totals = {key: Decimal('0.00') for key, _ in fee_heads}
    standard_total_amount = Decimal('0.00')
    agreed_total_amount = Decimal('0.00')
    missing_structure_classes = []
    agreed_fees = None
    form = None

    if selected_session:
        class_counts = linked_students.values('student_class_id').annotate(count=Count('id'))
        class_id_to_count = {row['student_class_id']: row['count'] for row in class_counts if row['student_class_id']}

        structures = FeesStructure.objects.filter(
            session=selected_session,
            class_code_id__in=class_id_to_count.keys(),
        ).select_related('class_code')
        structure_by_class = {fs.class_code_id: fs for fs in structures}

        for class_id, count in class_id_to_count.items():
            structure = structure_by_class.get(class_id)
            if not structure:
                missing_class = Class.objects.filter(id=class_id).first()
                if missing_class:
                    missing_structure_classes.append(missing_class.class_code or missing_class.class_name)
                continue
            for account_field, structure_field in fee_heads:
                standard_totals[account_field] += getattr(structure, structure_field) * count

        standard_total_amount = sum(standard_totals.values(), Decimal('0.00'))

        # Build per-student fee breakdown for display
        student_breakdowns = {key: [] for key, _ in fee_heads}
        for student in linked_students:
            structure = structure_by_class.get(student.student_class_id) if student.student_class_id else None
            class_label = (student.student_class.class_code or student.student_class.class_name) if student.student_class else 'N/A'
            for account_field, structure_field in fee_heads:
                amount = getattr(structure, structure_field) if structure else Decimal('0.00')
                student_breakdowns[account_field].append({
                    'name': student.first_name,
                    'class_label': class_label,
                    'amount': amount,
                })

        agreed_fees, _ = FeesAccountAgreement.objects.get_or_create(
            fees_account=fees_account,
            session=selected_session,
            defaults=standard_totals,
        )
        agreed_total_amount = agreed_fees.total_fees

        if request.method == 'POST':
            form = FeesAccountAgreementForm(request.POST, instance=agreed_fees)
            if form.is_valid():
                form.save()
                messages.success(request, 'Agreed fees saved for this account.')
                return redirect(f'{reverse("fee_account_agreement", args=[fees_account.id])}?session={selected_session.id}')
        else:
            form = FeesAccountAgreementForm(instance=agreed_fees)
    else:
        messages.warning(request, 'Please select a session to load standard and agreed fees.')

    return render(request, 'students/student_fee_agreement.html', {
        'fees_account': fees_account,
        'linked_students': linked_students,
        'sessions': sessions,
        'selected_session': selected_session,
        'standard_totals': standard_totals,
        'standard_total_amount': standard_total_amount,
        'agreed_total_amount': agreed_total_amount,
        'agreed_fees': agreed_fees,
        'form': form,
        'missing_structure_classes': missing_structure_classes,
        'student_breakdowns': student_breakdowns if selected_session else {},
    })


def fee_status_account_wise(request):
    """Account-wise fee status: payable vs paid vs balance by session."""
    sessions = Session.objects.all().order_by('-session')
    fee_accounts = FeesAccount.objects.all().order_by('account_id')
    selected_session_id = (request.GET.get('session') or '').strip()
    selected_account_id = (request.GET.get('account_id') or '').strip()
    selected_class_id = (request.GET.get('class_id') or '').strip()
    selected_student_id = (request.GET.get('student_id') or '').strip()

    students_filter_qs = Student.objects.select_related('student_class', 'fees_account').filter(fees_account__isnull=False)
    if selected_session_id:
        students_filter_qs = students_filter_qs.filter(session_id=selected_session_id)

    class_ids = students_filter_qs.values_list('student_class_id', flat=True).distinct()
    classes_for_filter = Class.objects.filter(id__in=class_ids).order_by('age')

    if selected_class_id:
        students_filter_qs = students_filter_qs.filter(student_class_id=selected_class_id)

    students_for_filter = students_filter_qs.order_by('first_name', 'last_name')
    account_ids_from_student_filters = None
    if selected_student_id:
        selected_student = students_for_filter.filter(id=selected_student_id).first()
        if selected_student and selected_student.fees_account_id:
            account_ids_from_student_filters = [selected_student.fees_account_id]
        else:
            account_ids_from_student_filters = []
    elif selected_class_id:
        account_ids_from_student_filters = list(students_for_filter.values_list('fees_account_id', flat=True).distinct())

    agreements_qs = FeesAccountAgreement.objects.select_related('session', 'fees_account')
    payments_qs = Income.objects.filter(fees_account__isnull=False, session__isnull=False)

    if selected_session_id:
        agreements_qs = agreements_qs.filter(session_id=selected_session_id)
        payments_qs = payments_qs.filter(session_id=selected_session_id)
    if account_ids_from_student_filters is not None:
        agreements_qs = agreements_qs.filter(fees_account_id__in=account_ids_from_student_filters)
        payments_qs = payments_qs.filter(fees_account_id__in=account_ids_from_student_filters)
    if selected_account_id:
        agreements_qs = agreements_qs.filter(fees_account_id=selected_account_id)
        payments_qs = payments_qs.filter(fees_account_id=selected_account_id)

    rows_by_key = {}

    for agreement in agreements_qs:
        key = (agreement.session_id, agreement.fees_account_id)
        rows_by_key[key] = {
            'session': agreement.session,
            'fees_account': agreement.fees_account,
            'payable_fee': agreement.total_fees,
            'paid_fee': Decimal('0.00'),
        }

    payment_totals = payments_qs.values('session_id', 'fees_account_id').annotate(total_paid=Sum('amount'))
    session_map = Session.objects.in_bulk([row['session_id'] for row in payment_totals])
    account_map = FeesAccount.objects.in_bulk([row['fees_account_id'] for row in payment_totals])

    for row in payment_totals:
        key = (row['session_id'], row['fees_account_id'])
        paid_amount = row['total_paid'] or Decimal('0.00')
        if key in rows_by_key:
            rows_by_key[key]['paid_fee'] = paid_amount
        else:
            rows_by_key[key] = {
                'session': session_map.get(row['session_id']),
                'fees_account': account_map.get(row['fees_account_id']),
                'payable_fee': Decimal('0.00'),
                'paid_fee': paid_amount,
            }

    rows = list(rows_by_key.values())
    for row in rows:
        row['balance_fee'] = row['payable_fee'] - row['paid_fee']

    # Build student + class summary per (session, account) for display in the report.
    session_ids = {r['session'].id for r in rows if r.get('session')}
    account_ids = {r['fees_account'].id for r in rows if r.get('fees_account')}
    student_qs = Student.objects.select_related('student_class').filter(
        session_id__in=session_ids,
        fees_account_id__in=account_ids,
    )
    students_by_key = {}
    for student in student_qs:
        key = (student.session_id, student.fees_account_id)
        class_label = 'N/A'
        if student.student_class:
            class_label = student.student_class.class_code or student.student_class.class_name or 'N/A'
        students_by_key.setdefault(key, []).append(f"{student.first_name} {student.last_name} - {class_label}")

    for row in rows:
        session_obj = row.get('session')
        account_obj = row.get('fees_account')
        key = (session_obj.id, account_obj.id) if session_obj and account_obj else None
        row['students_class_text'] = ', '.join(students_by_key.get(key, [])) if key else ''

    rows.sort(key=lambda r: (r['session'].session if r['session'] else '', r['fees_account'].account_id if r['fees_account'] else ''), reverse=True)

    total_payable = sum((r['payable_fee'] for r in rows), Decimal('0.00'))
    total_paid = sum((r['paid_fee'] for r in rows), Decimal('0.00'))
    total_balance = total_payable - total_paid

    return render(request, 'students/fee_status_account_wise.html', {
        'rows': rows,
        'sessions': sessions,
        'fee_accounts': fee_accounts,
        'classes_for_filter': classes_for_filter,
        'students_for_filter': students_for_filter,
        'selected_session_id': selected_session_id,
        'selected_account_id': selected_account_id,
        'selected_class_id': selected_class_id,
        'selected_student_id': selected_student_id,
        'total_payable': total_payable,
        'total_paid': total_paid,
        'total_balance': total_balance,
    })


def fees_statement_parents(request):
    """Fees Statement for Parents: 4 panels - account info, all-session summary, agreed fees, payment transactions."""
    current_session = Session.objects.filter(status='current_session').first()
    fee_accounts = FeesAccount.objects.all().order_by('account_id')
    classes = Class.objects.all().order_by('age')

    selected_account_id = (request.GET.get('account_id') or '').strip()
    selected_class_id = (request.GET.get('class_id') or '').strip()
    selected_student_id = (request.GET.get('student_id') or '').strip()

    # Build students dropdown (filtered by class)
    students_qs = Student.objects.select_related('student_class', 'fees_account').filter(fees_account__isnull=False)
    if selected_class_id:
        students_qs = students_qs.filter(student_class_id=selected_class_id)
    students_for_filter = students_qs.order_by('first_name', 'last_name')

    # Resolve the fees account to display
    selected_account = None
    if selected_account_id:
        selected_account = FeesAccount.objects.filter(pk=selected_account_id).first()
    elif selected_student_id:
        student_obj = Student.objects.select_related('fees_account').filter(pk=selected_student_id).first()
        if student_obj and student_obj.fees_account:
            selected_account = student_obj.fees_account

    # Panel 1 – Account Name + Student details in the account (current session)
    account_students = []
    if selected_account and current_session:
        account_students = list(
            Student.objects.filter(fees_account=selected_account, session=current_session)
            .select_related('student_class')
            .order_by('primary_account_holder', 'first_name', 'last_name')
        )

    # Shared head map used by Panel 2 and Panel 3
    FEES_HEAD_MAP = [
        # (agreement_field, structure_field)
        ('tuition_fees',   'fee_tuition'),
        ('tc_fees',        'fee_tc'),
        ('admission_fees', 'fee_admission'),
        ('book_set',       'book_set'),
        ('book_diary',     'book_diary'),
        ('book_other',     'book_other'),
        ('uniform_shirt',  'uniform_shirt'),
        ('uniform_pant',   'uniform_pant'),
        ('uniform_sweater','uniform_sweater'),
        ('uniform_hoody',  'uniform_hoody'),
        ('uniform_t_shirt','uniform_t_shirt'),
        ('uniform_tie',    'uniform_tie'),
        ('uniform_belt',   'uniform_belt'),
        ('uniform_id_card','uniform_id_card'),
        ('bus_fees',       None),
    ]

    def _school_fees_for_session(account, session_obj, agreement):
        """Sum FeesStructure amounts (only for heads where agreed fee != 0) for all students in this account+session."""
        if agreement is None:
            return Decimal('0.00')
        students_in_session = list(
            Student.objects.filter(fees_account=account, session=session_obj)
            .values('student_class_id')
        )
        class_counts = {}
        for s in students_in_session:
            cid = s['student_class_id']
            if cid:
                class_counts[cid] = class_counts.get(cid, 0) + 1
        if not class_counts:
            return Decimal('0.00')
        structures = {
            fs.class_code_id: fs
            for fs in FeesStructure.objects.filter(
                session=session_obj,
                class_code_id__in=class_counts.keys(),
            )
        }
        total = Decimal('0.00')
        for agr_field, str_field in FEES_HEAD_MAP:
            if str_field is None:
                continue
            agreed_amt = getattr(agreement, agr_field, Decimal('0.00')) or Decimal('0.00')
            if agreed_amt == Decimal('0.00'):
                continue
            for class_id, count in class_counts.items():
                fs = structures.get(class_id)
                if fs:
                    total += getattr(fs, str_field, Decimal('0.00')) * count
        return total

    # Panel 2 – Summary of payments across all sessions
    payment_summary = []
    summary_total_payable = Decimal('0.00')
    summary_total_paid = Decimal('0.00')
    summary_total_school = Decimal('0.00')
    if selected_account:
        agreements = list(
            FeesAccountAgreement.objects.filter(fees_account=selected_account)
            .select_related('session')
            .order_by('-session__session')
        )
        payments_by_session = Income.objects.filter(
            fees_account=selected_account
        ).values('session_id').annotate(total_paid=Sum('amount'))
        payments_map = {row['session_id']: row['total_paid'] or Decimal('0.00') for row in payments_by_session}
        seen_session_ids = set()
        for agreement in agreements:
            paid = payments_map.get(agreement.session_id, Decimal('0.00'))
            payable = agreement.total_fees
            school = _school_fees_for_session(selected_account, agreement.session, agreement)
            payment_summary.append({
                'session': agreement.session,
                'school': school,
                'payable': payable,
                'paid': paid,
                'balance': payable - paid,
            })
            seen_session_ids.add(agreement.session_id)
            summary_total_payable += payable
            summary_total_paid += paid
            summary_total_school += school
        # Payments without an agreement
        for session_id, paid in payments_map.items():
            if session_id not in seen_session_ids:
                session_obj = Session.objects.filter(pk=session_id).first()
                payment_summary.append({
                    'session': session_obj,
                    'school': Decimal('0.00'),
                    'payable': Decimal('0.00'),
                    'paid': paid,
                    'balance': -paid,
                })
                summary_total_paid += paid
        payment_summary.sort(
            key=lambda r: r['session'].session if r['session'] else '',
            reverse=True,
        )

    summary_total_balance = summary_total_payable - summary_total_paid

    # Panel 3 – Agreed fees grid for current session (non-zero heads only)
    # Labels aligned with FEES_HEAD_MAP order
    PANEL3_LABELS = [
        'Tuition Fees', 'TC Fees', 'Admission Fees',
        'Book Set', 'Book Diary', 'Book (Other)',
        'Uniform – Shirt', 'Uniform – Pant', 'Uniform – Sweater',
        'Uniform – Hoody', 'Uniform – T-Shirt', 'Uniform – Tie',
        'Uniform – Belt', 'Uniform – ID Card', 'Bus Fees',
    ]
    agreed_fees = None
    fee_heads = []
    p3_school_total = Decimal('0.00')
    if selected_account and current_session:
        agreed_fees = FeesAccountAgreement.objects.filter(
            fees_account=selected_account, session=current_session
        ).first()
    if agreed_fees:
        # Compute standard school fees per head from FeesStructure
        p3_students = account_students or list(
            Student.objects.filter(fees_account=selected_account, session=current_session)
            .select_related('student_class')
        )
        class_counts = {}
        for st in p3_students:
            if st.student_class_id:
                class_counts[st.student_class_id] = class_counts.get(st.student_class_id, 0) + 1
        structures = {}
        if class_counts:
            for fs in FeesStructure.objects.filter(
                session=current_session,
                class_code_id__in=class_counts.keys(),
            ):
                structures[fs.class_code_id] = fs

        def school_fee_for(str_field):
            if str_field is None:
                return Decimal('0.00')
            total = Decimal('0.00')
            for class_id, count in class_counts.items():
                fs = structures.get(class_id)
                if fs:
                    total += getattr(fs, str_field, Decimal('0.00')) * count
            return total

        for label, (agr_field, str_field) in zip(PANEL3_LABELS, FEES_HEAD_MAP):
            agreed_amt = getattr(agreed_fees, agr_field, Decimal('0.00')) or Decimal('0.00')
            if agreed_amt == Decimal('0.00'):
                continue
            school_amt = school_fee_for(str_field)
            fee_heads.append((label, school_amt, agreed_amt))
            p3_school_total += school_amt

    # Panel 4 – Payment transactions from income ledger (current session only)
    income_transactions = []
    income_total = Decimal('0.00')
    if selected_account and current_session:
        income_transactions = list(
            Income.objects.filter(fees_account=selected_account, session=current_session)
            .order_by('date', 'id')
        )
        income_total = sum((t.amount for t in income_transactions), Decimal('0.00'))

    return render(request, 'students/fees_statement_parents.html', {
        'fee_accounts': fee_accounts,
        'classes': classes,
        'students_for_filter': students_for_filter,
        'selected_account_id': selected_account_id,
        'selected_class_id': selected_class_id,
        'selected_student_id': selected_student_id,
        'selected_account': selected_account,
        'current_session': current_session,
        # Panel 1
        'account_students': account_students,
        # Panel 2
        'payment_summary': payment_summary,
        'summary_total_school': summary_total_school,
        'summary_total_payable': summary_total_payable,
        'summary_total_paid': summary_total_paid,
        'summary_total_balance': summary_total_balance,
        # Panel 3
        'agreed_fees': agreed_fees,
        'fee_heads': fee_heads,
        'p3_school_total': p3_school_total,
        # Panel 4
        'income_transactions': income_transactions,
        'income_total': income_total,
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
    session_filter = request.GET.get('session_filter', '')
    class_filter = request.GET.get('class_filter', '')
    student_name_filter = request.GET.get('student_name_filter', '')

    if session_filter:
        students_no_account = students_no_account.filter(session_id=session_filter)
    if class_filter:
        students_no_account = students_no_account.filter(student_class_id=class_filter)
    if student_name_filter:
        students_no_account = students_no_account.filter(
            Q(first_name__icontains=student_name_filter) | Q(last_name__icontains=student_name_filter)
        )
    
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
                    
                    # Get all students in current session and class
                    current_students = Student.objects.filter(
                        session=current_session,
                        student_class=current_class
                    )
                    
                    promoted_count = 0
                    for student in current_students:
                        student.session = new_session
                        student.student_class = new_class
                        student.save(update_fields=['session', 'student_class', 'updated_at'])
                        promoted_count += 1
                    
                    messages.success(request, f"Successfully promoted {promoted_count} students from {current_class.class_code} ({current_session.session}) to {new_class.class_code} ({new_session.session})")
                    
                except Exception as e:
                    messages.error(request, f"Error during promotion: {str(e)}")

        elif action == 'promote_fee':
            from dailyLedger.models import FeesStructure
            current_session_id = request.POST.get('current_session')
            new_session_id = request.POST.get('new_session')
            current_class_id = request.POST.get('current_class')

            if current_session_id and new_session_id and current_class_id:
                try:
                    current_session = Session.objects.get(id=current_session_id)
                    new_session = Session.objects.get(id=new_session_id)
                    current_class = Class.objects.get(id=current_class_id)

                    source = FeesStructure.objects.filter(session=current_session, class_code=current_class).first()
                    if not source:
                        messages.warning(request, f"No fee structure found for {current_class.class_code} ({current_session.session}).")
                    else:
                        fee_fields = [
                            'fee_tuition', 'fee_tc', 'fee_admission',
                            'book_set', 'book_diary', 'book_other',
                            'uniform_shirt', 'uniform_pant', 'uniform_sweater',
                            'uniform_hoody', 'uniform_t_shirt', 'uniform_tie',
                            'uniform_belt', 'uniform_id_card',
                        ]
                        defaults = {f: getattr(source, f) for f in fee_fields}
                        obj, created = FeesStructure.objects.update_or_create(
                            session=new_session,
                            class_code=current_class,
                            defaults=defaults,
                        )
                        action_word = "Created" if created else "Updated"
                        messages.success(request, f"{action_word} fee structure for {current_class.class_code} ({new_session.session}) copied from ({current_session.session}).")

                except Exception as e:
                    messages.error(request, f"Error during fee promotion: {str(e)}")

        elif action == 'promote_account':
            current_session_id = request.POST.get('current_session')
            new_session_id = request.POST.get('new_session')
            fees_account_val = request.POST.get('fees_account')

            if current_session_id and new_session_id and fees_account_val:
                try:
                    current_session = Session.objects.get(id=current_session_id)
                    new_session = Session.objects.get(id=new_session_id)

                    agreement_fields = [
                        'tuition_fees', 'tc_fees', 'admission_fees',
                        'book_set', 'book_diary', 'book_other',
                        'uniform_shirt', 'uniform_pant', 'uniform_sweater',
                        'uniform_hoody', 'uniform_t_shirt', 'uniform_tie',
                        'uniform_belt', 'uniform_id_card', 'bus_fees',
                    ]

                    if fees_account_val == '__all__':
                        sources = FeesAccountAgreement.objects.filter(session=current_session)
                    else:
                        account = FeesAccount.objects.get(id=fees_account_val)
                        sources = FeesAccountAgreement.objects.filter(session=current_session, fees_account=account)

                    promoted_count = 0
                    for source in sources:
                        defaults = {f: getattr(source, f) for f in agreement_fields}
                        obj, created = FeesAccountAgreement.objects.update_or_create(
                            fees_account=source.fees_account,
                            session=new_session,
                            defaults=defaults,
                        )
                        promoted_count += 1

                    action_word = "Created/updated"
                    messages.success(request, f"{action_word} {promoted_count} fees account(s) for {new_session.session} copied from {current_session.session}.")

                except Exception as e:
                    messages.error(request, f"Error during account promotion: {str(e)}")
    
    # Get data for dropdowns — show all sessions so user can promote between any two
    active_sessions = Session.objects.all().order_by('-session')
    new_sessions = Session.objects.all().order_by('-session')

    # Default selections
    default_current_session = Session.objects.filter(status='current_session').first()
    default_new_session = Session.objects.filter(status='next_session').first()
    classes = Class.objects.all().order_by('age')
    fees_accounts = FeesAccount.objects.filter(account_status='open').order_by('account_id')

    context = {
        'active_sessions': active_sessions,
        'new_sessions': new_sessions,
        'classes': classes,
        'fees_accounts': fees_accounts,
        'default_current_session': default_current_session,
        'default_new_session': default_new_session,
    }

    return render(request, 'students/promote_session.html', context)
