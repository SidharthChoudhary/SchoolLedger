# SchoolLedger Architecture

## 1. System Overview

SchoolLedger is a Django 6.0 web application for managing a schools operations: students, employees, fee accounts, and financial ledgers (income and expenses).

The system is implemented as a single Django project with several domain-focused apps:

- accounts  authentication, roles, and user profiles
- dailyLedger  income and expense ledger, financial heads, sessions, fee structures
- students  student master data, fee accounts, class and session mappings, attendance
- employees  employee master data, attendance, salary registers and manual adjustments
- website  public or home pages and general site navigation

## 2. Deployment and Runtime

- **Framework:** Django 6.0, Python (see requirements.txt).
- **Entry points:**
  - Development server: `python manage.py runserver`.
  - WSGI: `schoolapp.wsgi.application`.
  - ASGI: `schoolapp.asgi.application` (for async support if needed).
- **Database:**
  - Default: SQLite, using db.sqlite3 via `django.db.backends.sqlite3`.
  - Production: likely MySQL (see MYSQL_CONFIGURATION.txt and deployment docs) if or when configured.
- **Static and media files:**
  - Static URL: `/static/`, with collected files under `staticfiles/` for production.
  - Media URL: `/media/`, with uploaded files stored under the `media/` directory.
- **Sessions and authentication:**
  - Uses Djangos built-in auth and session frameworks.
  - Sessions expire on browser close and time out after 30 minutes of inactivity.
  - After successful login, users are redirected to the `home` view (defined in the website app).

## 3. High-Level Module Architecture

### 3.1 Project configuration (schoolapp)

- **Settings (schoolapp/settings.py)**
  - Registers the core Django apps and project apps: accounts, dailyLedger, website, employees, students.
  - Configures middleware: Security, Sessions, Common, CSRF, Authentication, Messages, Clickjacking.
  - Defines database, static, media, and session configuration.

- **URLs (schoolapp/urls.py)**
  - `admin/`  Django admin site.
  - `accounts/`  account and RBAC-related views (login, role management, etc.).
  - `` (root)  website app URLs (home and public views).
  - `ledger-expense/`  dailyLedger URLs for expense ledger functionality.
  - `ledger-income/...`  income ledger views and JSON APIs, including:
    - `ledger-income/api/classes/<session_id>/`  fetch classes for a session.
    - `ledger-income/api/students/<session_id>/<class_id>/`  fetch students for a given class and session.
    - `ledger-income/api/student-srn/<student_id>/`  fetch a students SRN.
    - `ledger-income/api/fee-account/<srn>/`  resolve a students fee account by SRN.
    - `ledger-income/bulk-import-ledger/`  bulk import income ledger entries.
    - `ledger-income/download-ledger-template/`  download a CSV template for bulk import.
    - `ledger-income/`  income home view.
    - `ledger-income/delete/<pk>/`  delete income entries.
  - `employees/`  employees app URLs.
  - `students/`  students app URLs.
  - Serves media files in development via `static(settings.MEDIA_URL, settings.MEDIA_ROOT)`.

### 3.2 Domain apps overview

At a high level, the apps are responsible for:

- **accounts:** User roles and profiles, role-based access control on top of Django auth.
- **dailyLedger:** Financial ledger for income and expenses, accounting heads, academic sessions, and fee structures.
- **students:** Student master records, fee accounts, academic class mappings, and student attendance.
- **employees:** Employee records, attendance, and salary computation/adjustments.
- **website:** Site-level pages and navigation, including the main `home` view.

## 4. Domain Model Overview

### 4.1 Financial ledger and sessions (dailyLedger)

Key models in dailyLedger/models.py:

- **LedgerEntryBase (abstract)**
  - Common fields for financial entries:
    - `voucher_number`, `date`, `amount`, `details`.
    - `major_head`, `head`, `sub_head` (classification of the transaction).
    - `payment_type` (Cash, Credit, Against Credit).
    - `session` (FK to Session) to tie each entry to an academic/financial session.
    - Timestamp fields for `created_at`.
  - Common ordering: most recent date and ID first.

- **Expense (LedgerEntryBase)**
  - Concrete model representing expense-side ledger entries.
  - Inherits all fields from LedgerEntryBase and uses similar ordering.

- **Income (LedgerEntryBase)**
  - Concrete model representing income-side ledger entries.
  - Adds `fees_account` (FK to `students.FeesAccount`) to associate fee-based income with a specific student fee account.
  - Custom manager `IncomeManager` optimizes queries by deferring `payment_type` and using `select_related('fees_account')`.
  - Auto-generates `voucher_number` (e.g., V1001, V1002, ...) when not provided, based on the highest existing voucher.

- **Head**
  - Defines financial heads for classifying ledger entries.
  - Key fields:
    - `major_head`, `head`, `sub_head`.
    - `ledger_type` (Expense or Income).
    - `status` (Active or Inactive).
  - Uniqueness is enforced across (`major_head`, `head`, `sub_head`).

- **Session**
  - Represents an academic or financial session (for example, `2024-2025`).
  - Fields:
    - `session` (unique string)
    - `status`  `next_session`, `current_session`, or `old_session`.
    - `created_at` timestamp.
  - Frequently referenced by other apps as the time dimension for data.

- **FeesStructure**
  - Stores the fee structure per (`session`, `class_code`).
  - Fields include:
    - Tuition and TC fees.
    - Admission fees.
    - Book-related charges.
    - Uniform components (shirt, pant, tie, belt, ID card).
  - Ensures only one fees structure per (`session`, `class_code`), and provides a basis for calculating `StudentAccount` data.

### 4.2 Students and academic data (students)

Key models in students/models.py:

- **Class**
  - Represents school grades or classes.
  - Fields: `class_name`, `class_code`, and `age`.
  - Ordered by `age` and used for organizing students and fees structures.

- **Student**
  - Stores personal and academic information for each student.
  - Personal details: `first_name`, `last_name`, `date_of_birth`, `gender`, parents/guardians and contact numbers, medical and dietary information.
  - Academic:
    - `student_class` (FK to Class).
    - `transport_method` (whether the student uses the school bus).
    - `previous_school`.
    - `srn` (Student Registration Number, unique).
    - `rte` (Right to Education flag).
    - `primary_account_holder`.
    - `session` (FK to dailyLedger.Session).
  - Finance:
    - `fees_account` (FK to FeesAccount) linking the student to a fee account.
  - Media:
    - `image` stored under `media/students/`.
  - Helpers:
    - `name` property returns full name for backward compatibility.
    - `fee_account_name` property creates a formatted account name from FeesAccount and SRN when the student is marked as the primary account holder.

- **StudentAccount**
  - Per (`student`, `session`) record for tracking fee components.
  - Fee fields: tuition, TC, book-related amounts, admission fees, and uniform components.
  - `total_fees` property calculates the total amount due by summing all components.

- **FeesAccount**
  - Represents a logical fee account used to receive and track payments.
  - Fields:
    - `account_id` (auto-generated sequential identifier, zero-padded).
    - `name` (human-friendly account name).
    - `account_open` and optional `account_close` dates.
    - `account_status` (open/closed).
    - `register_page` reference (optional).
  - Central to linking students and income ledger entries.

- **SessionClassStudentMap**
  - Master mapping between `session`, `student_class`, and `student`.
  - Tracks SRN and a promotion date.
  - Enforces uniqueness per (`session`, `student_class`, `student`).
  - Auto-populates `srn` from the related Student on save.

- **StudentAttendance**
  - Tracks daily attendance for students.
  - Key fields:
    - `session`, `student_class`, `student`, `date`, and `attendance` (present/absent).
  - Enforces uniqueness per (`session`, `student`, `date`).
  - Forms the basis for daily and period-based attendance reporting.

### 4.3 Employees and HR data (employees)

Key models in employees/models.py:

- **Employee**
  - Employee master record.
  - Fields cover identification, contact, address, qualification, experience, previous institute, post, gender, joining and leaving dates, status, and salary details (`base_salary_per_month`, `leaves_entitled`).
  - `emp_no` is auto-generated as a sequential number (starting from 1000) using the current maximum `emp_no` + 1.
  - `emp_image` is stored under `media/employees/`.

- **EmployeeAttendance**
  - Tracks daily employee attendance.
  - Fields:
    - `session`, `date`, `employee`, `attendance` (present, absent, half-day, leave).
  - Enforces uniqueness for (`session`, `date`, `employee`).

- **EmployeeRegister**
  - Monthly salary register for each employee per session.
  - Fields:
    - `session`, `employee`, `month` (YYYY-MM), `paid_days`, `payable_salary`.
  - Business logic in `save()`:
    - If `paid_days >= (30 - entitled_leaves)` then pay full base salary.
    - Otherwise, compute `payable_salary` on a pro-rata basis: `paid_days * (base_salary / 30)`.

- **ManualSalaryData**
  - Tracks manual salary-related adjustments, including old dues.
  - Fields:
    - `session`, `employee`, `amount_type` (salary, old_due, other), `amount`, `month`, and an optional `note`.
  - Intended to complement or override automatic salary calculations when needed.

### 4.4 Accounts and role-based access control (accounts)

Key models in accounts/models.py:

- **Role**
  - Custom role model for role-based access control.
  - Supported roles include: super_admin, admin, principal, accountant, teacher, and support_staff.
  - Each role can have many Django `Permission` objects assigned via a many-to-many relationship.

- **UserRole**
  - Through-model mapping a Django `User` to a `Role`.
  - Allows tracking when roles were assigned and by whom (`assigned_by`).
  - Enforces uniqueness per (`user`, `role`).

- **UserProfile**
  - One-to-one extension of Djangos built-in `User` model.
  - Adds: full name, phone, gender, profile image, department, verification flag, last login IP, and timestamps.
  - Helper methods:
    - `get_roles`, `get_role_display_names`, `get_all_permissions`.
    - `has_role`, `has_any_role`, `has_all_roles`.
    - `has_permission`, `has_any_permission`.
    - Convenience checks: `is_super_admin`, `is_admin`, `is_principal`, `is_accountant`, `is_teacher`, `is_support_staff`.
  - These helpers are designed to be used in views and templates for authorization checks.

### 4.5 Website app (website)

- The website app (urls, views, and templates) provides the general site pages, including the `home` page where `LOGIN_REDIRECT_URL` points.
- It integrates with accounts (for logged-in views) and links to the other apps for navigation.

## 5. Cross-App Relationships

- **Session (dailyLedger.Session)**
  - Central time dimension for the system.
  - Referenced by:
    - Student (`session`), StudentAccount, SessionClassStudentMap, StudentAttendance.
    - EmployeeRegister, EmployeeAttendance, ManualSalaryData.
    - LedgerEntryBase via the `session` FK in Expense and Income.

- **FeesAccount (students.FeesAccount)**
  - Linked from `Student` and `Income`.
  - Connects student accounts to financial income ledger entries.

- **Class (students.Class)**
  - Used by: Student, FeesStructure (as `class_code`), SessionClassStudentMap, and StudentAttendance.

- **User and roles (accounts + auth)**
  - Django `User` is extended by UserProfile and connected to Role via UserRole.
  - Views and templates should rely on UserProfile helper methods for authorization rather than accessing permissions directly.

## 6. Typical Business Flows

### 6.1 Student onboarding

1. Create a Student record and assign:
   - Class (Class),
   - Session (Session),
   - SRN and personal details.
2. Create or link a FeesAccount for the student (marking `primary_account_holder` where applicable).
3. Use the FeesStructure for the given (`session`, `class_code`) to populate a StudentAccount for that (`student`, `session`).
4. Create a SessionClassStudentMap entry to bind the student, class, and session together.

### 6.2 Recording fee income

1. When fees are received, create an Income entry:
   - Link it to the appropriate FeesAccount.
   - Set `major_head`, `head`, and `sub_head` to classify the transaction.
   - Associate it with the relevant Session.
2. If no voucher number is supplied, the system auto-generates one.
3. IncomeManager optimizes queries for typical list and report views.

### 6.3 Recording expenses

1. Create Expense entries for each outgoing payment.
2. Classify the expense via Head (major_head, head, sub_head).
3. Associate the entry with the applicable Session.

### 6.4 Attendance tracking

- **Students:**
  - For each day and class, record StudentAttendance with the appropriate status and session.
  - Use this data to report attendance per day, per class, or per session.

- **Employees:**
  - For each working day, record EmployeeAttendance with status and session.
  - This data feeds into monthly salary computation.

### 6.5 Payroll and salary adjustments

1. For each employee and month, maintain an EmployeeRegister record with:
   - Session, employee, month, and paid_days.
   - Automatically computed payable_salary based on paid_days and entitled leaves.
2. Use ManualSalaryData entries to record special cases:
   - Old dues.
   - One-off salary adjustments.
   - Other manual corrections.
3. Corresponding expense ledger entries (Expense) can be created to reflect salary payouts and adjustments in the financial ledger.

## 7. Security and Access Control

- **Authentication:**
  - Standard Django auth (username/password, optional admin site).

- **Authorization (RBAC):**
  - Role-based access using Role, UserRole, and Permission.
  - Views and templates can check:
    - Specific roles via UserProfile methods (`is_admin()`, `is_accountant()`, etc.).
    - Specific permissions via `has_permission()` or `has_any_permission()`.

- **Session security:**
  - Sessions expire at browser close and after a fixed idle time window (30 minutes), reducing risk from abandoned sessions.

## 8. Local Development Notes (high level)

- **Run development server:**
  - From the project root, run: `python manage.py runserver`.
- **Apply migrations:**
  - `python manage.py migrate`
- **Create a superuser:**
  - `python manage.py createsuperuser`
- **Static and media:**
  - In development, static and media files are served directly by Django (for production, use `collectstatic` and a real web server).

You can extend this document over time with:

- Detailed sequence diagrams for critical flows (admissions, fee collection, payroll).
- A permissions matrix mapping roles to permissions and views.
- Environment-specific notes (development, staging, production) and deployment steps.
