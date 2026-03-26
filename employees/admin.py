from django.contrib import admin
from .models import Employee, EmployeeAttendance, EmployeePayrollEntry

class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('emp_no', 'name', 'post', 'status', 'joining_date')
    list_filter = ('status', 'post', 'joining_date')
    search_fields = ('name', 'emp_no', 'contact_number')
    readonly_fields = ('emp_no', 'created_at')

class EmployeeAttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'session', 'date', 'attendance')
    list_filter = ('session', 'date', 'attendance')
    search_fields = ('employee__name',)
    date_hierarchy = 'date'

class EmployeePayrollEntryAdmin(admin.ModelAdmin):
    list_display = ('employee', 'session', 'month', 'payable_salary', 'old_dues', 'other_amount')
    list_filter = ('session', 'month')
    search_fields = ('employee__name',)
    readonly_fields = ('created_at', 'updated_at')

admin.site.register(Employee, EmployeeAdmin)
admin.site.register(EmployeeAttendance, EmployeeAttendanceAdmin)
admin.site.register(EmployeePayrollEntry, EmployeePayrollEntryAdmin)
