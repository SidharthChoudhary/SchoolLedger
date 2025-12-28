from django.contrib import admin
from .models import Student, StudentAccount, Class, FeesAccount, StudentAttendance


@admin.register(Class)
class ClassAdmin(admin.ModelAdmin):
    list_display = ['id', 'class_name', 'age']
    search_fields = ['class_name']
    ordering = ['age']


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['name', 'date_of_birth', 'student_class', 'gender', 'transport_method']
    list_filter = ['student_class', 'gender', 'transport_method']
    search_fields = ['name', 'fathers_name', 'mothers_name']


@admin.register(StudentAccount)
class StudentAccountAdmin(admin.ModelAdmin):
    list_display = ['student', 'session', 'total_fees']
    list_filter = ['session', 'student__student_class']
    search_fields = ['student__name']


@admin.register(FeesAccount)
class FeesAccountAdmin(admin.ModelAdmin):
    list_display = ['account_id', 'name', 'account_open', 'account_status', 'account_close']
    list_filter = ['account_status', 'account_open']
    search_fields = ['account_id', 'name']
    readonly_fields = ['account_id', 'created_at', 'updated_at']


@admin.register(StudentAttendance)
class StudentAttendanceAdmin(admin.ModelAdmin):
    list_display = ['student', 'student_class', 'session', 'date', 'attendance']
    list_filter = ['session', 'student_class', 'attendance', 'date']
    search_fields = ['student__first_name', 'student__last_name']
