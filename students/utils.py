import csv
from datetime import datetime
from io import StringIO

from dailyLedger.models import Session

from .models import Class, Student


TRUE_VALUES = {'1', 'true', 'yes', 'y'}


def _parse_bool(value):
    if value is None:
        return False
    return str(value).strip().lower() in TRUE_VALUES


def _parse_date(value, field_name, row_num, results):
    text = (value or '').strip()
    if not text:
        return None

    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%m/%d/%Y'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    results['errors'].append((row_num, f"Invalid {field_name} format: '{text}'"))
    return None


def _get_class(class_code, class_name):
    if class_code:
        match = Class.objects.filter(class_code__iexact=class_code).first()
        if match:
            return match

    if class_name:
        return Class.objects.filter(class_name__iexact=class_name).first()

    return None


def _get_session(session_label):
    if not session_label:
        return None
    return Session.objects.filter(session__iexact=session_label).first()


def parse_csv_students(csv_content, handle_duplicates='error'):
    results = {
        'valid_rows': [],
        'errors': [],
        'warnings': [],
        'duplicate_rows': [],
    }

    try:
        reader = csv.DictReader(StringIO(csv_content))

        if reader.fieldnames is None:
            results['errors'].append((0, 'CSV file is empty'))
            return results

        actual_headers = {h.lower().strip() if h else '' for h in reader.fieldnames}
        required_headers = {
            'first_name',
            'last_name',
            'gender',
            'fathers_name',
            'mothers_name',
            'class_code',
            'session',
        }

        if not required_headers.issubset(actual_headers):
            missing = sorted(required_headers - actual_headers)
            results['errors'].append((0, f"Missing required columns: {', '.join(missing)}"))
            return results

        for row_num, row in enumerate(reader, start=2):
            normalized = {k.lower().strip(): (v.strip() if v else '') for k, v in row.items()}

            first_name = normalized.get('first_name', '')
            last_name = normalized.get('last_name', '')
            gender = normalized.get('gender', '').lower()
            fathers_name = normalized.get('fathers_name', '')
            mothers_name = normalized.get('mothers_name', '')

            class_code = normalized.get('class_code', '')
            class_name = normalized.get('class_name', '')
            session_label = normalized.get('session', '')

            srn = normalized.get('srn', '') or None
            date_of_birth = _parse_date(normalized.get('date_of_birth', ''), 'Date_of_Birth', row_num, results)
            admission_date = _parse_date(normalized.get('admission_date', ''), 'Admission_Date', row_num, results)

            if not first_name or not last_name:
                results['errors'].append((row_num, 'First_Name and Last_Name are required'))
                continue
            if gender not in {'male', 'female', '3rd_gender'}:
                results['errors'].append((row_num, "Gender must be one of: male, female, 3rd_gender"))
                continue
            if not fathers_name or not mothers_name:
                results['errors'].append((row_num, "Fathers_Name and Mothers_Name are required"))
                continue

            school_class = _get_class(class_code, class_name)
            if not school_class:
                results['errors'].append((row_num, f"Class not found for class_code='{class_code}' class_name='{class_name}'"))
                continue

            session_obj = _get_session(session_label)
            if not session_obj:
                results['errors'].append((row_num, f"Session not found: '{session_label}'"))
                continue

            if any(err_row == row_num for err_row, _ in results['errors']):
                continue

            data = {
                'first_name': first_name,
                'last_name': last_name,
                'gender': gender,
                'fathers_name': fathers_name,
                'mothers_name': mothers_name,
                'gardians_name': normalized.get('gardians_name', '') or None,
                'fathers_phone': normalized.get('fathers_phone', '') or None,
                'mothers_phone': normalized.get('mothers_phone', '') or None,
                'gardians_phone': normalized.get('gardians_phone', '') or None,
                'student_class': school_class,
                'session': session_obj,
                'transport_method': _parse_bool(normalized.get('transport_method', '')),
                'previous_school': normalized.get('previous_school', '') or None,
                'srn': srn,
                'admission_date': admission_date,
                'date_of_birth': date_of_birth,
                'rte': _parse_bool(normalized.get('rte', '')),
                'primary_account_holder': _parse_bool(normalized.get('primary_account_holder', '')),
                'medical_conditions': normalized.get('medical_conditions', '') or None,
                'dietary_restrictions': normalized.get('dietary_restrictions', '') or None,
            }

            if srn:
                duplicate = Student.objects.filter(srn=srn).exists()
                duplicate_desc = f'Duplicate SRN: {srn}'
                match_filters = {'srn': srn}
            else:
                match_filters = {
                    'first_name__iexact': first_name,
                    'last_name__iexact': last_name,
                    'fathers_name__iexact': fathers_name,
                    'session': session_obj,
                }
                duplicate = Student.objects.filter(**match_filters).exists()
                duplicate_desc = 'Duplicate name + father + session'

            if duplicate:
                if handle_duplicates == 'error':
                    results['errors'].append((row_num, duplicate_desc))
                elif handle_duplicates == 'skip':
                    results['warnings'].append((row_num, f'{duplicate_desc} (will be skipped)'))
                    results['duplicate_rows'].append((row_num, data, match_filters))
                else:
                    results['warnings'].append((row_num, f'{duplicate_desc} (will be updated)'))
                    results['duplicate_rows'].append((row_num, data, match_filters))
            else:
                results['valid_rows'].append((row_num, data))

    except Exception as exc:
        results['errors'].append((0, f'Error reading CSV file: {exc}'))

    return results


def import_students(valid_rows, duplicate_rows, handle_duplicates='skip'):
    result = {
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'errors': [],
    }

    for row_num, data in valid_rows:
        try:
            Student.objects.create(**data)
            result['created'] += 1
        except Exception as exc:
            result['errors'].append((row_num, f'Failed to create: {exc}'))

    for row_num, data, match_filters in duplicate_rows:
        if handle_duplicates == 'update':
            try:
                student = Student.objects.filter(**match_filters).first()
                if not student:
                    Student.objects.create(**data)
                    result['created'] += 1
                    continue

                for key, value in data.items():
                    setattr(student, key, value)
                student.save()
                result['updated'] += 1
            except Exception as exc:
                result['errors'].append((row_num, f'Failed to update: {exc}'))
        else:
            result['skipped'] += 1

    return result
