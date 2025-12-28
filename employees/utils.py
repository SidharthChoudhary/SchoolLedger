import csv
from io import StringIO
from datetime import datetime
from .models import Employee


def parse_csv_employees(csv_content, handle_duplicates='skip'):
    """
    Parse CSV file for Employee import.
    
    Expected columns: Name, DOB, Contact_Number, Gender, Qualification, Address, 
                     Experience_Years, Previous_Institute, Post, Role, Role_Detail, 
                     Joining_Date, Base_Salary_Per_Month, Status, Leaves_Entitled
    
    Returns: {
        'valid_rows': [(data_dict, row_num), ...],
        'errors': [(row_num, error_message), ...],
        'warnings': [(row_num, warning_message), ...],
        'duplicate_rows': [(row_num, data_dict), ...]
    }
    """
    results = {
        'valid_rows': [],
        'errors': [],
        'warnings': [],
        'duplicate_rows': [],
    }
    
    try:
        f = StringIO(csv_content)
        reader = csv.DictReader(f)
        
        if reader.fieldnames is None:
            results['errors'].append((0, "CSV file is empty"))
            return results
        
        # Normalize header names
        expected_headers = {'name', 'joining_date'}  # Only Name is truly required
        actual_headers = {h.lower().strip() if h else '' for h in reader.fieldnames}
        
        if not expected_headers.issubset(actual_headers):
            missing = expected_headers - actual_headers
            results['errors'].append((0, f"Missing required columns: {', '.join(missing)}"))
            return results
        
        # Process rows
        for row_num, row in enumerate(reader, start=2):
            try:
                row_normalized = {k.lower().strip(): v.strip() if v else '' for k, v in row.items()}
                
                # Extract fields
                name = row_normalized.get('name', '').strip()
                dob_str = row_normalized.get('dob', '').strip()
                contact_number = row_normalized.get('contact_number', '').strip()
                gender = row_normalized.get('gender', '').strip()
                qualification = row_normalized.get('qualification', '').strip()
                address = row_normalized.get('address', '').strip()
                experience_years_str = row_normalized.get('experience_years', '').strip()
                previous_institute = row_normalized.get('previous_institute', '').strip()
                post = row_normalized.get('post', '').strip()
                role = row_normalized.get('role', '').strip()
                role_detail = row_normalized.get('role_detail', '').strip()
                joining_date_str = row_normalized.get('joining_date', '').strip()
                base_salary_str = row_normalized.get('base_salary_per_month', '').strip()
                status = row_normalized.get('status', 'active').strip()
                leaves_entitled_str = row_normalized.get('leaves_entitled', '0').strip()
                
                # Validate required fields
                if not name:
                    results['errors'].append((row_num, "Name is required"))
                    continue
                
                # Validate and parse dates
                dob = None
                if dob_str:
                    try:
                        dob = datetime.strptime(dob_str, '%Y-%m-%d').date()
                    except ValueError:
                        results['errors'].append((row_num, f"Invalid DOB format: '{dob_str}' (use YYYY-MM-DD)"))
                        continue
                
                joining_date = None
                if joining_date_str:
                    try:
                        joining_date = datetime.strptime(joining_date_str, '%Y-%m-%d').date()
                    except ValueError:
                        results['errors'].append((row_num, f"Invalid Joining_Date format: '{joining_date_str}' (use YYYY-MM-DD)"))
                        continue
                
                # Validate and parse numeric fields
                experience_years = 0
                if experience_years_str:
                    try:
                        experience_years = float(experience_years_str)
                    except ValueError:
                        results['errors'].append((row_num, f"Invalid Experience_Years: '{experience_years_str}'"))
                        continue
                
                base_salary = 0
                if base_salary_str:
                    try:
                        base_salary = float(base_salary_str)
                    except ValueError:
                        results['errors'].append((row_num, f"Invalid Base_Salary_Per_Month: '{base_salary_str}'"))
                        continue
                
                leaves_entitled = 0
                if leaves_entitled_str:
                    try:
                        leaves_entitled = int(leaves_entitled_str)
                    except ValueError:
                        results['errors'].append((row_num, f"Invalid Leaves_Entitled: '{leaves_entitled_str}'"))
                        continue
                
                # Validate gender
                if gender and gender not in ['M', 'F', 'O']:
                    results['errors'].append((row_num, f"Invalid Gender: '{gender}' (must be M, F, or O)"))
                    continue
                
                # Validate status (convert to lowercase)
                status = status.lower() if status else 'active'
                if status and status not in ['active', 'inactive', 'left']:
                    results['errors'].append((row_num, f"Invalid Status: '{status}' (must be 'active', 'inactive', or 'left')"))
                    continue
                
                # Check for duplicates (by name and joining_date)
                duplicate = Employee.objects.filter(
                    name=name,
                    joining_date=joining_date
                ).exists()
                
                data = {
                    'name': name,
                    'dob': dob,
                    'contact_number': contact_number,
                    'gender': gender,
                    'qualification': qualification,
                    'address': address,
                    'experience_years': experience_years,
                    'previous_institute': previous_institute,
                    'post': post,
                    'role': role,
                    'role_detail': role_detail,
                    'joining_date': joining_date,
                    'base_salary_per_month': base_salary,
                    'status': status or 'active',
                    'leaves_entitled': leaves_entitled,
                }
                
                if duplicate:
                    if handle_duplicates == 'error':
                        results['errors'].append((row_num, "Duplicate record (combination of Name and Joining_Date already exists)"))
                    elif handle_duplicates == 'skip':
                        results['warnings'].append((row_num, "Duplicate record (will be skipped)"))
                        results['duplicate_rows'].append((row_num, data))
                    elif handle_duplicates == 'update':
                        results['warnings'].append((row_num, "Duplicate record (will be updated)"))
                        results['duplicate_rows'].append((row_num, data))
                else:
                    results['valid_rows'].append((data, row_num))
            
            except Exception as e:
                results['errors'].append((row_num, f"Error parsing row: {str(e)}"))
    
    except Exception as e:
        results['errors'].append((0, f"Error reading CSV file: {str(e)}"))
    
    return results


def import_employees(valid_rows, duplicate_rows, handle_duplicates='skip'):
    """
    Import valid Employee rows into the database.
    
    Returns: {
        'created': count,
        'updated': count,
        'skipped': count,
        'errors': [(row_num, error_message), ...]
    }
    """
    result = {
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'errors': [],
    }
    
    # Import valid rows (new records)
    for data, row_num in valid_rows:
        try:
            Employee.objects.create(**data)
            result['created'] += 1
        except Exception as e:
            result['errors'].append((row_num, f"Failed to create: {str(e)}"))
    
    # Handle duplicates
    for row_num, data in duplicate_rows:
        if handle_duplicates == 'update':
            try:
                employee, _ = Employee.objects.get_or_create(
                    name=data['name'],
                    joining_date=data['joining_date'],
                    defaults=data
                )
                # Update the found employee with new data
                for key, value in data.items():
                    setattr(employee, key, value)
                employee.save()
                result['updated'] += 1
            except Exception as e:
                result['errors'].append((row_num, f"Failed to update: {str(e)}"))
        else:  # skip
            result['skipped'] += 1
    
    return result


def parse_csv_manual_salary_data(csv_content, handle_duplicates='skip'):
    """
    Parse CSV file for Manual Salary Data import.
    
    Expected columns: Session, Employee_Name, Amount_Type, Amount, Month, Note
    
    Returns: {
        'valid_rows': [(data_dict, row_num), ...],
        'errors': [(row_num, error_message), ...],
        'warnings': [(row_num, warning_message), ...],
        'duplicate_rows': [(row_num, data_dict), ...]
    }
    """
    from datetime import datetime
    from .models import ManualSalaryData
    from dailyLedger.models import Session
    
    results = {
        'valid_rows': [],
        'errors': [],
        'warnings': [],
        'duplicate_rows': [],
    }
    
    try:
        f = StringIO(csv_content)
        reader = csv.DictReader(f)
        
        if reader.fieldnames is None:
            results['errors'].append((0, "CSV file is empty"))
            return results
        
        # Normalize header names
        expected_headers = {'session', 'employee_name', 'amount_type', 'amount', 'month'}
        actual_headers = {h.lower().strip() if h else '' for h in reader.fieldnames}
        
        if not expected_headers.issubset(actual_headers):
            missing = expected_headers - actual_headers
            results['errors'].append((0, f"Missing required columns: {', '.join(missing)}"))
            return results
        
        # Process rows
        for row_num, row in enumerate(reader, start=2):
            try:
                row_normalized = {k.lower().strip(): v.strip() if v else '' for k, v in row.items()}
                
                # Extract fields
                session_name = row_normalized.get('session', '').strip()
                employee_name = row_normalized.get('employee_name', '').strip()
                amount_type = row_normalized.get('amount_type', '').strip().lower()
                amount_str = row_normalized.get('amount', '').strip()
                month = row_normalized.get('month', '').strip()
                note = row_normalized.get('note', '').strip()
                
                # Validate required fields
                if not session_name:
                    results['errors'].append((row_num, "Session is required"))
                    continue
                if not employee_name:
                    results['errors'].append((row_num, "Employee_Name is required"))
                    continue
                if not amount_type:
                    results['errors'].append((row_num, "Amount_Type is required"))
                    continue
                if not amount_str:
                    results['errors'].append((row_num, "Amount is required"))
                    continue
                if not month:
                    results['errors'].append((row_num, "Month is required"))
                    continue
                
                # Get session
                try:
                    session = Session.objects.get(session=session_name)
                except Session.DoesNotExist:
                    results['errors'].append((row_num, f"Session '{session_name}' not found"))
                    continue
                
                # Get employee
                try:
                    employee = Employee.objects.get(name=employee_name)
                except Employee.DoesNotExist:
                    results['errors'].append((row_num, f"Employee '{employee_name}' not found"))
                    continue
                
                # Validate amount
                try:
                    amount = float(amount_str)
                except ValueError:
                    results['errors'].append((row_num, f"Invalid Amount: '{amount_str}'"))
                    continue
                
                # Validate amount_type
                if amount_type not in ['salary', 'old_due', 'other']:
                    results['errors'].append((row_num, f"Invalid Amount_Type: '{amount_type}' (must be 'salary', 'old_due', or 'other')"))
                    continue
                
                # Validate month format
                try:
                    datetime.strptime(month, '%Y-%m')
                except ValueError:
                    results['errors'].append((row_num, f"Invalid Month format: '{month}' (use YYYY-MM)"))
                    continue
                
                # Check for duplicates
                duplicate = ManualSalaryData.objects.filter(
                    session=session,
                    employee=employee,
                    month=month,
                    amount_type=amount_type
                ).exists()
                
                data = {
                    'session_id': session.id,
                    'employee_id': employee.id,
                    'amount_type': amount_type,
                    'amount': amount,
                    'month': month,
                    'note': note,
                }
                
                if duplicate:
                    if handle_duplicates == 'error':
                        results['errors'].append((row_num, "Duplicate record (combination of Session, Employee, Month, Amount_Type already exists)"))
                    elif handle_duplicates == 'skip':
                        results['warnings'].append((row_num, "Duplicate record (will be skipped)"))
                        results['duplicate_rows'].append((row_num, data))
                    elif handle_duplicates == 'update':
                        results['warnings'].append((row_num, "Duplicate record (will be updated)"))
                        results['duplicate_rows'].append((row_num, data))
                else:
                    results['valid_rows'].append((data, row_num))
            
            except Exception as e:
                results['errors'].append((row_num, f"Error parsing row: {str(e)}"))
    
    except Exception as e:
        results['errors'].append((0, f"Error reading CSV file: {str(e)}"))
    
    return results


def import_manual_salary_data(valid_rows, duplicate_rows, handle_duplicates='skip'):
    """
    Import valid Manual Salary Data rows into the database.
    
    Returns: {
        'created': count,
        'updated': count,
        'skipped': count,
        'errors': [(row_num, error_message), ...]
    }
    """
    from .models import ManualSalaryData
    from dailyLedger.models import Session
    
    result = {
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'errors': [],
    }
    
    # Import valid rows (new records)
    for data, row_num in valid_rows:
        try:
            ManualSalaryData.objects.create(**data)
            result['created'] += 1
        except Exception as e:
            result['errors'].append((row_num, f"Failed to create: {str(e)}"))
    
    # Handle duplicates
    for row_num, data in duplicate_rows:
        if handle_duplicates == 'update':
            try:
                obj, _ = ManualSalaryData.objects.get_or_create(
                    session_id=data['session_id'],
                    employee_id=data['employee_id'],
                    month=data['month'],
                    amount_type=data['amount_type'],
                    defaults=data
                )
                # Update the found record with new data
                for key, value in data.items():
                    setattr(obj, key, value)
                obj.save()
                result['updated'] += 1
            except Exception as e:
                result['errors'].append((row_num, f"Failed to update: {str(e)}"))
        else:  # skip
            result['skipped'] += 1
    
    return result

