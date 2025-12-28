from django.contrib import admin
from django.contrib.auth.models import User
from .models import Role, UserRole, UserProfile


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'display_name', 'description')
    filter_horizontal = ('permissions',)
    fieldsets = (
        ('Role Information', {
            'fields': ('name', 'display_name', 'description')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Permissions', {
            'fields': ('permissions',),
            'description': 'Select permissions to assign to this role'
        }),
    )
    readonly_fields = ('created_at', 'updated_at')


class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 1
    fields = ('role', 'assigned_at', 'assigned_by')
    readonly_fields = ('assigned_at',)
    
    def get_readonly_fields(self, request, obj=None):
        # Make assigned_by editable only by superusers
        if not request.user.is_superuser:
            return self.readonly_fields + ['assigned_by']
        return self.readonly_fields


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('get_username', 'full_name', 'department', 'get_roles_display', 'is_verified')
    list_filter = ('is_verified', 'created_at', 'gender')
    search_fields = ('user__username', 'full_name', 'email', 'department')
    readonly_fields = ('user', 'created_at', 'updated_at', 'last_login_ip')
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'full_name', 'email')
        }),
        ('Contact Information', {
            'fields': ('phone', 'department', 'bio')
        }),
        ('Personal Details', {
            'fields': ('gender', 'profile_image')
        }),
        ('Status', {
            'fields': ('is_verified', 'last_login_ip')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = 'Username'
    
    def get_roles_display(self, obj):
        roles = list(obj.get_role_display_names())
        return ', '.join(roles) if roles else 'No roles assigned'
    get_roles_display.short_description = 'Roles'
    
    def email(self, obj):
        return obj.user.email


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_role_display', 'assigned_at', 'assigned_by')
    list_filter = ('role', 'assigned_at')
    search_fields = ('user__username', 'role__display_name')
    readonly_fields = ('assigned_at',)
    
    def get_role_display(self, obj):
        return obj.role.display_name
    get_role_display.short_description = 'Role'
