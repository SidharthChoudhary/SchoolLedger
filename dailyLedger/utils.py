import csv
from io import StringIO
from .models import Head


def parse_csv_account_heads(csv_content, handle_duplicates='skip'):
    """
    Parse CSV file for Account Heads import.
    
    Expected columns: Ledger_Type, Major_Head, Head, Sub_Head, (optional) Status, (optional) Details
    
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
        # Parse CSV
        f = StringIO(csv_content)
        reader = csv.DictReader(f)
        
        if reader.fieldnames is None:
            results['errors'].append((0, "CSV file is empty"))
            return results
        
        # Normalize header names
        expected_headers = {'ledger_type', 'major_head', 'head', 'sub_head'}
        actual_headers = {h.lower().strip() if h else '' for h in reader.fieldnames}
        
        if not expected_headers.issubset(actual_headers):
            missing = expected_headers - actual_headers
            results['errors'].append((0, f"Missing required columns: {', '.join(missing)}"))
            return results
        
        # Process rows
        for row_num, row in enumerate(reader, start=2):  # Start at 2 (header is row 1)
            try:
                # Normalize keys
                row_normalized = {k.lower().strip(): v.strip() if v else '' for k, v in row.items()}
                
                # Extract fields
                ledger_type = row_normalized.get('ledger_type', '').strip()
                major_head = row_normalized.get('major_head', '').strip()
                head = row_normalized.get('head', '').strip()
                sub_head = row_normalized.get('sub_head', '').strip()
                status = row_normalized.get('status', 'Active').strip()
                details = row_normalized.get('details', '').strip()
                
                # Validate required fields
                if not ledger_type:
                    results['errors'].append((row_num, "Ledger_Type is required"))
                    continue
                if not major_head:
                    results['errors'].append((row_num, "Major_Head is required"))
                    continue
                if not head:
                    results['errors'].append((row_num, "Head is required"))
                    continue
                
                # Validate ledger_type
                if ledger_type not in ['Expense', 'Income']:
                    results['errors'].append((row_num, f"Invalid Ledger_Type: '{ledger_type}' (must be 'Expense' or 'Income')"))
                    continue
                
                # Validate status
                if status and status not in ['Active', 'Inactive']:
                    results['errors'].append((row_num, f"Invalid Status: '{status}' (must be 'Active' or 'Inactive')"))
                    continue
                
                # Check for duplicates
                duplicate = Head.objects.filter(
                    ledger_type=ledger_type,
                    major_head=major_head,
                    head=head,
                    sub_head=sub_head or ''
                ).exists()
                
                data = {
                    'ledger_type': ledger_type,
                    'major_head': major_head,
                    'head': head,
                    'sub_head': sub_head,
                    'status': status or 'Active',
                    'details': details,
                }
                
                if duplicate:
                    if handle_duplicates == 'error':
                        results['errors'].append((row_num, "Duplicate record (combination of Ledger_Type, Major_Head, Head, Sub_Head already exists)"))
                    elif handle_duplicates == 'skip':
                        results['warnings'].append((row_num, "Duplicate record (will be skipped)"))
                        results['duplicate_rows'].append((row_num, data))
                    elif handle_duplicates == 'update':
                        results['warnings'].append((row_num, "Duplicate record (will be updated)"))
                        results['duplicate_rows'].append((row_num, data))
                    else:
                        results['valid_rows'].append((row_num, data))
                else:
                    results['valid_rows'].append((row_num, data))
            
            except Exception as e:
                results['errors'].append((row_num, f"Error parsing row: {str(e)}"))
    
    except Exception as e:
        results['errors'].append((0, f"Error reading CSV file: {str(e)}"))
    
    return results


def import_account_heads(valid_rows, duplicate_rows, handle_duplicates='skip'):
    """
    Import valid Account Heads rows into the database.
    
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
    for row_num, data in valid_rows:
        try:
            Head.objects.create(
                ledger_type=data['ledger_type'],
                major_head=data['major_head'],
                head=data['head'],
                sub_head=data['sub_head'],
                status=data.get('status', 'Active'),
                details=data.get('details', ''),
            )
            result['created'] += 1
        except Exception as e:
            result['errors'].append((row_num, f"Failed to create: {str(e)}"))
    
    # Handle duplicates
    for row_num, data in duplicate_rows:
        if handle_duplicates == 'update':
            try:
                obj, _ = Head.objects.get_or_create(
                    ledger_type=data['ledger_type'],
                    major_head=data['major_head'],
                    head=data['head'],
                    sub_head=data['sub_head'],
                    defaults={
                        'ledger_type': data['ledger_type'],
                        'major_head': data['major_head'],
                        'head': data['head'],
                        'sub_head': data['sub_head'],
                        'status': data.get('status', 'Active'),
                        'details': data.get('details', ''),
                    }
                )
                result['updated'] += 1
            except Exception as e:
                result['errors'].append((row_num, f"Failed to update: {str(e)}"))
        else:  # skip
            result['skipped'] += 1
    
    return result


def parse_csv_ledger_entries(csv_content, handle_duplicates='skip', ledger_type='Expense'):
    """
    Parse CSV file for Ledger Entries import.
    
    Expected columns: Voucher_Number, Date, Amount, Major_Head, Head, Sub_Head, Payment_Type, Session, Details
    
    Sub_Head contains the account/employee name (for salary entries, this is the employee name)
    
    ledger_type: 'Expense' or 'Income' - determines which model to use for duplicate checking
    
    Returns: {
        'valid_rows': [(row_num, data_dict), ...],
        'errors': [(row_num, error_message), ...],
        'warnings': [(row_num, warning_message), ...],
        'duplicate_rows': [(row_num, data_dict), ...]
    }
    """
    from datetime import datetime
    from .models import Expense, Income, Session
    
    # Select the model based on ledger_type
    model = Income if ledger_type == 'Income' else Expense
    
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
        expected_headers = {'voucher_number', 'date', 'amount', 'major_head', 'head', 'sub_head', 'payment_type'}
        actual_headers = {h.lower().strip() if h else '' for h in reader.fieldnames}
        
        if not expected_headers.issubset(actual_headers):
            missing = expected_headers - actual_headers
            results['errors'].append((0, f"Missing required columns: {', '.join(missing)}"))
            return results
        
        # Process rows
        for row_num, row in enumerate(reader, start=2):
            try:
                row_normalized = {k.lower().strip(): v.strip() if v else '' for k, v in row.items()}
                
                # Extract and validate fields
                voucher_number = row_normalized.get('voucher_number', '').strip()
                date_str = row_normalized.get('date', '').strip()
                amount_str = row_normalized.get('amount', '').strip()
                major_head = row_normalized.get('major_head', '').strip()
                head = row_normalized.get('head', '').strip()
                sub_head = row_normalized.get('sub_head', '').strip()
                payment_type = row_normalized.get('payment_type', '').strip()
                session_name = row_normalized.get('session', '').strip()
                details = row_normalized.get('details', '').strip()
                
                # Validate required fields
                if not date_str:
                    results['errors'].append((row_num, "Date is required"))
                    continue
                if not amount_str:
                    results['errors'].append((row_num, "Amount is required"))
                    continue
                if not sub_head:
                    results['errors'].append((row_num, "Sub_Head (account/employee name) is required"))
                    continue
                
                # Validate date format
                try:
                    entry_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    results['errors'].append((row_num, f"Invalid date format: '{date_str}' (use YYYY-MM-DD)"))
                    continue
                
                # Validate amount
                try:
                    amount = float(amount_str)
                except ValueError:
                    results['errors'].append((row_num, f"Invalid amount: '{amount_str}'"))
                    continue
                
                # Validate payment_type
                if payment_type and payment_type not in ['Cash', 'Credit', 'Against Credit', 'Bank Transfer']:
                    results['errors'].append((row_num, f"Invalid Payment_Type: '{payment_type}' (must be 'Cash', 'Credit', 'Against Credit', or 'Bank Transfer')"))
                    continue
                
                # Get session if provided
                session_id = None
                if session_name:
                    try:
                        session = Session.objects.get(session=session_name)
                        session_id = session.id
                    except Session.DoesNotExist:
                        results['warnings'].append((row_num, f"Session '{session_name}' not found, will be skipped"))
                
                # Check for duplicates (by voucher_number, date, major_head, head, sub_head)
                duplicate = model.objects.filter(
                    voucher_number=voucher_number,
                    date=entry_date,
                    major_head=major_head,
                    head=head,
                    sub_head=sub_head or ''
                ).exists() if voucher_number else False
                
                data = {
                    'voucher_number': voucher_number,
                    'date': entry_date,
                    'amount': amount,
                    'account_name': sub_head,
                    'major_head': major_head,
                    'head': head,
                    'sub_head': sub_head,
                    'payment_type': payment_type or 'Cash',
                    'session_id': session_id,
                    'details': details,
                }
                
                if duplicate:
                    if handle_duplicates == 'error':
                        results['errors'].append((row_num, "Duplicate record (combination of Voucher_Number, Date, Major_Head, Head, Sub_Head already exists)"))
                    elif handle_duplicates == 'skip':
                        results['warnings'].append((row_num, "Duplicate record (will be skipped)"))
                        results['duplicate_rows'].append((row_num, data))
                    elif handle_duplicates == 'update':
                        results['warnings'].append((row_num, "Duplicate record (will be updated)"))
                        results['duplicate_rows'].append((row_num, data))
                else:
                    results['valid_rows'].append((row_num, data))
            
            except Exception as e:
                results['errors'].append((row_num, f"Error parsing row: {str(e)}"))
    
    except Exception as e:
        results['errors'].append((0, f"Error reading CSV file: {str(e)}"))
    
    return results


def import_ledger_entries(valid_rows, duplicate_rows, handle_duplicates='skip', ledger_type='Expense'):
    """
    Import valid Ledger Entries into the database.
    
    ledger_type: 'Expense' or 'Income' - determines which model to use
    
    Returns: {
        'created': count,
        'updated': count,
        'skipped': count,
        'errors': [(row_num, error_message), ...]
    }
    """
    from .models import Expense, Income
    
    # Select the model based on ledger_type
    model = Income if ledger_type == 'Income' else Expense
    
    result = {
        'created': 0,
        'updated': 0,
        'skipped': 0,
        'errors': [],
    }
    
    # Import valid rows (new records)
    for row_num, data in valid_rows:
        try:
            model.objects.create(
                voucher_number=data['voucher_number'],
                date=data['date'],
                amount=data['amount'],
                major_head=data['major_head'],
                head=data['head'],
                sub_head=data['sub_head'],
                payment_type=data['payment_type'],
                session_id=data['session_id'],
                details=data['details'],
            )
            result['created'] += 1
        except Exception as e:
            result['errors'].append((row_num, f"Failed to create: {str(e)}"))
    
    # Handle duplicates
    for row_num, data in duplicate_rows:
        if handle_duplicates == 'update':
            try:
                model.objects.filter(
                    voucher_number=data['voucher_number'],
                    date=data['date']
                ).update(
                    amount=data['amount'],
                    major_head=data['major_head'],
                    head=data['head'],
                    sub_head=data['sub_head'],
                    payment_type=data['payment_type'],
                    session_id=data['session_id'],
                    details=data['details'],
                )
                result['updated'] += 1
            except Exception as e:
                result['errors'].append((row_num, f"Failed to update: {str(e)}"))
        else:  # skip
            result['skipped'] += 1
    
    return result
