from django.contrib import admin
from .models import Employee, EmployeeRegister, EmployeeAttendance, ManualSalaryData

class EmployeeAdmin(admin.ModelAdmin):
    list_display = ('emp_no', 'name', 'post', 'status', 'joining_date')
    list_filter = ('status', 'post', 'joining_date')
    search_fields = ('name', 'emp_no', 'contact_number')
    readonly_fields = ('emp_no', 'created_at')

class EmployeeRegisterAdmin(admin.ModelAdmin):
    list_display = ('employee', 'session', 'month_display', 'paid_days', 'payable_salary')
    list_filter = ('session', 'month')
    search_fields = ('employee__name',)
    readonly_fields = ('payable_salary',)

class EmployeeAttendanceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'session', 'date', 'attendance')
    list_filter = ('session', 'date', 'attendance')
    search_fields = ('employee__name',)
    date_hierarchy = 'date'
    
    # Add quick link to attendance rally
    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['title'] = 'Employee Attendance'
        return super().changelist_view(request, extra_context)

class ManualSalaryDataAdmin(admin.ModelAdmin):
    list_display = ('employee', 'session', 'month', 'amount_type', 'note')
    list_filter = ('session', 'amount_type', 'month')
    search_fields = ('employee__name',)
    readonly_fields = ('created_at', 'updated_at')

admin.site.register(Employee, EmployeeAdmin)
admin.site.register(EmployeeRegister, EmployeeRegisterAdmin)
admin.site.register(EmployeeAttendance, EmployeeAttendanceAdmin)
admin.site.register(ManualSalaryData, ManualSalaryDataAdmin)
