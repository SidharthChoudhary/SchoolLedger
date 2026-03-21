from django.urls import path
from .views import (
    employees_home, delete_employee, bulk_import_employees, download_employees_template,
    employee_register, delete_register, manual_salary_data, delete_manual_salary_data,
    bulk_import_manual_salary_data, download_manual_salary_data_template,
    employee_attendance, delete_attendance, attendance_rally,
    export_employees_csv, delete_all_employees, employee_profile,
    employee_full_salary_statement, employees_salary_statement,
)
from . import views

urlpatterns = [
    path("", employees_home, name="employees_home"),
    path("delete/<int:pk>/", delete_employee, name="delete_employee"),
    path("export-csv/", export_employees_csv, name="export_employees_csv"),
    path("delete-all/", delete_all_employees, name="delete_all_employees"),
    path("bulk-import/", bulk_import_employees, name="bulk_import_employees"),
    path("download-template/", download_employees_template, name="download_employees_template"),
    path("manual-salary-data/", manual_salary_data, name="manual_salary_data"),
    path("manual-salary-data/bulk-import/", bulk_import_manual_salary_data, name="bulk_import_manual_salary_data"),
    path("manual-salary-data/download-template/", download_manual_salary_data_template, name="download_manual_salary_data_template"),
    path("manual-salary-data/delete/<int:pk>/", delete_manual_salary_data, name="delete_manual_salary_data"),
    path("view/", views.employees_view, name="employees_view"),
    path("view/<int:pk>/", employee_profile, name="employee_profile"),
    path("register/", employee_register, name="employee_register"),
    path("register/delete/<int:pk>/", delete_register, name="delete_register"),
    path("attendance/", employee_attendance, name="employee_attendance"),
    path("attendance/delete/<int:pk>/", delete_attendance, name="delete_attendance"),
    path("attendance-rally/", attendance_rally, name="attendance_rally"),
    path("salary-statement/", employee_full_salary_statement, name="employee_full_salary_statement"),
    path("employees-salary-statement/", employees_salary_statement, name="employees_salary_statement"),
]