from functools import wraps
from django.shortcuts import render
from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import login_required


def role_required(*role_names):
    """
    Decorator to restrict view access based on user roles.
    Usage: @role_required('admin', 'accountant')
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not hasattr(request.user, 'profile'):
                return render(request, 'accounts/access_denied.html', 
                            {'reason': 'User profile not found'}, status=403)
            
            # Super admin has access to everything
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Check if user has any of the required roles
            if request.user.profile.has_any_role(role_names):
                return view_func(request, *args, **kwargs)
            
            return render(request, 'accounts/access_denied.html',
                        {'reason': f'Requires one of: {", ".join(role_names)}'}, 
                        status=403)
        return wrapper
    return decorator


def permission_required(permission_codename):
    """
    Decorator to restrict view access based on permissions.
    Usage: @permission_required('ledger.view_expense')
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not hasattr(request.user, 'profile'):
                return render(request, 'accounts/access_denied.html',
                            {'reason': 'User profile not found'}, status=403)
            
            # Super admin has access to everything
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Check if user has the permission
            if request.user.profile.has_permission(permission_codename):
                return view_func(request, *args, **kwargs)
            
            return render(request, 'accounts/access_denied.html',
                        {'reason': f'Requires permission: {permission_codename}'}, 
                        status=403)
        return wrapper
    return decorator


def any_permission_required(*permission_codenames):
    """
    Decorator to restrict view access based on any of multiple permissions.
    Usage: @any_permission_required('ledger.view_expense', 'ledger.edit_expense')
    """
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not hasattr(request.user, 'profile'):
                return render(request, 'accounts/access_denied.html',
                            {'reason': 'User profile not found'}, status=403)
            
            # Super admin has access to everything
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Check if user has any of the permissions
            if request.user.profile.has_any_permission(permission_codenames):
                return view_func(request, *args, **kwargs)
            
            return render(request, 'accounts/access_denied.html',
                        {'reason': f'Requires one of: {", ".join(permission_codenames)}'}, 
                        status=403)
        return wrapper
    return decorator


class RoleRequiredMixin:
    """
    Mixin for class-based views that require specific roles.
    Usage: class MyView(RoleRequiredMixin, ListView): required_roles = ['admin']
    """
    required_roles = []
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return render(request, 'accounts/access_denied.html',
                        {'reason': 'Authentication required'}, status=403)
        
        if not hasattr(request.user, 'profile'):
            return render(request, 'accounts/access_denied.html',
                        {'reason': 'User profile not found'}, status=403)
        
        # Super admin has access to everything
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        
        # Check if user has any of the required roles
        if request.user.profile.has_any_role(self.required_roles):
            return super().dispatch(request, *args, **kwargs)
        
        return render(request, 'accounts/access_denied.html',
                    {'reason': f'Requires one of: {", ".join(self.required_roles)}'}, 
                    status=403)


class PermissionRequiredMixin:
    """
    Mixin for class-based views that require specific permissions.
    Usage: class MyView(PermissionRequiredMixin, ListView): required_permission = 'ledger.view_expense'
    """
    required_permission = None
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return render(request, 'accounts/access_denied.html',
                        {'reason': 'Authentication required'}, status=403)
        
        if not hasattr(request.user, 'profile'):
            return render(request, 'accounts/access_denied.html',
                        {'reason': 'User profile not found'}, status=403)
        
        # Super admin has access to everything
        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)
        
        # Check if user has the permission
        if request.user.profile.has_permission(self.required_permission):
            return super().dispatch(request, *args, **kwargs)
        
        return render(request, 'accounts/access_denied.html',
                    {'reason': f'Requires permission: {self.required_permission}'}, 
                    status=403)
