from django.urls import path
from .views import (
    employees_home, delete_employee, bulk_import_employees, download_employees_template,
    employee_attendance, delete_attendance, attendance_rally,
    export_employees_csv, delete_all_employees, employee_profile,
    employee_full_salary_statement, employees_salary_statement,
    import_attendance_csv, download_attendance_template, attendance_register,
    employee_payroll_unified, delete_filtered_attendance,
    bulk_import_payroll, download_payroll_template, employee_salary_yearly,
    employee_salary_payment_record,
)
from . import views

urlpatterns = [
    path("", employees_home, name="employees_home"),
    path("delete/<int:pk>/", delete_employee, name="delete_employee"),
    path("export-csv/", export_employees_csv, name="export_employees_csv"),
    path("delete-all/", delete_all_employees, name="delete_all_employees"),
    path("bulk-import/", bulk_import_employees, name="bulk_import_employees"),
    path("download-template/", download_employees_template, name="download_employees_template"),
    path("view/", views.employees_view, name="employees_view"),
    path("view/<int:pk>/", employee_profile, name="employee_profile"),
    path("attendance-rally/", attendance_rally, name="attendance_rally"),
    path("attendance-rally/import-csv/", import_attendance_csv, name="import_attendance_csv"),
    path("attendance-rally/download-template/", download_attendance_template, name="download_attendance_template"),
    path("attendance-register/", attendance_register, name="attendance_register"),
    path("attendance-register/delete-filtered/", delete_filtered_attendance, name="delete_filtered_attendance"),
    path("salary-statement/", employee_full_salary_statement, name="employee_full_salary_statement"),
    path("employees-salary-statement/", employees_salary_statement, name="employees_salary_statement"),
    path("payroll/", employee_payroll_unified, name="employee_payroll_unified"),
    path("payroll/bulk-import/", bulk_import_payroll, name="bulk_import_payroll"),
    path("payroll/download-template/", download_payroll_template, name="download_payroll_template"),
    path("salary-yearly/", employee_salary_yearly, name="employee_salary_yearly"),
    path("salary-payment/", employee_salary_payment_record, name="employee_salary_payment_record"),
]