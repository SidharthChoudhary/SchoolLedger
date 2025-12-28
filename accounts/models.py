from django.db import models
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType


class Role(models.Model):
    """
    Custom role model for role-based access control.
    Each role can have multiple permissions.
    """
    ROLE_CHOICES = [
        ('super_admin', 'Super Admin'),
        ('admin', 'Admin'),
        ('principal', 'Principal'),
        ('accountant', 'Accountant'),
        ('teacher', 'Teacher'),
        ('support_staff', 'Support Staff'),
    ]
    
    name = models.CharField(
        max_length=100, 
        unique=True,
        choices=ROLE_CHOICES,
        help_text="Unique identifier for the role"
    )
    display_name = models.CharField(
        max_length=100,
        help_text="Display name for UI"
    )
    description = models.TextField(
        blank=True,
        help_text="Description of role responsibilities"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive roles cannot be assigned to users"
    )
    permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name='roles',
        help_text="Permissions assigned to this role"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
    
    def __str__(self):
        return self.display_name
    
    def get_permission_list(self):
        """Get all permission codenames for this role"""
        return list(self.permissions.values_list('codename', flat=True))


class UserRole(models.Model):
    """
    M2M through model linking User to Role.
    Allows tracking when roles were assigned.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_roles'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        related_name='user_assignments'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    assigned_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='roles_assigned'
    )
    
    class Meta:
        unique_together = ['user', 'role']
        ordering = ['-assigned_at']
        verbose_name = 'User Role'
        verbose_name_plural = 'User Roles'
    
    def __str__(self):
        return f"{self.user.username} - {self.role.display_name}"


class UserProfile(models.Model):
    """
    Extended user profile with additional information.
    """
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    full_name = models.CharField(
        max_length=255,
        help_text="Full name of the user"
    )
    phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Contact phone number"
    )
    gender = models.CharField(
        max_length=1,
        choices=GENDER_CHOICES,
        blank=True,
        help_text="Gender"
    )
    profile_image = models.ImageField(
        upload_to='profiles/',
        null=True,
        blank=True,
        help_text="Profile picture"
    )
    bio = models.TextField(
        blank=True,
        help_text="Short biography"
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        help_text="Department or designation"
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Email verification status"
    )
    last_login_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="Last login IP address"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'
    
    def __str__(self):
        return f"Profile of {self.user.username}"
    
    def get_roles(self):
        """Get all active roles for this user"""
        return self.user.user_roles.filter(
            role__is_active=True
        ).values_list('role__name', flat=True)
    
    def get_role_display_names(self):
        """Get display names of all active roles"""
        return self.user.user_roles.filter(
            role__is_active=True
        ).values_list('role__display_name', flat=True)
    
    def get_all_permissions(self):
        """Get all permissions from assigned roles"""
        roles = self.user.user_roles.filter(role__is_active=True)
        permissions = set()
        for user_role in roles:
            permissions.update(user_role.role.get_permission_list())
        return permissions
    
    def has_role(self, role_name):
        """Check if user has specific role"""
        return self.user.user_roles.filter(
            role__name=role_name,
            role__is_active=True
        ).exists()
    
    def has_any_role(self, role_names):
        """Check if user has any of the given roles"""
        if isinstance(role_names, str):
            role_names = [role_names]
        return self.user.user_roles.filter(
            role__name__in=role_names,
            role__is_active=True
        ).exists()
    
    def has_all_roles(self, role_names):
        """Check if user has all of the given roles"""
        if isinstance(role_names, str):
            role_names = [role_names]
        return (
            self.user.user_roles.filter(
                role__name__in=role_names,
                role__is_active=True
            ).count() == len(role_names)
        )
    
    def has_permission(self, permission_codename):
        """Check if user has specific permission through any role"""
        roles = self.user.user_roles.filter(role__is_active=True)
        return roles.filter(
            role__permissions__codename=permission_codename
        ).exists()
    
    def has_any_permission(self, permission_codenames):
        """Check if user has any of the given permissions"""
        if isinstance(permission_codenames, str):
            permission_codenames = [permission_codenames]
        roles = self.user.user_roles.filter(role__is_active=True)
        return roles.filter(
            role__permissions__codename__in=permission_codenames
        ).exists()
    
    def is_super_admin(self):
        """Check if user is super admin"""
        return self.has_role('super_admin')
    
    def is_admin(self):
        """Check if user is admin or super admin"""
        return self.has_any_role(['admin', 'super_admin'])
    
    def is_principal(self):
        """Check if user is principal"""
        return self.has_role('principal')
    
    def is_accountant(self):
        """Check if user is accountant"""
        return self.has_role('accountant')
    
    def is_teacher(self):
        """Check if user is teacher"""
        return self.has_role('teacher')
    
    def is_support_staff(self):
        """Check if user is support staff"""
        return self.has_role('support_staff')
