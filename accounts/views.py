from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.db.models import Q
from .models import Role, UserProfile, UserRole
from .decorators import role_required, RoleRequiredMixin
from .forms import UserProfileForm


# --- Function-based views ---

@login_required
@role_required('super_admin', 'admin', 'principal')
def user_list(request):
    """List all users with their roles"""
    users = User.objects.prefetch_related('user_roles__role').all()
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(profile__full_name__icontains=search_query)
        )
    
    context = {
        'users': users,
        'search_query': search_query,
    }
    return render(request, 'accounts/user_list.html', context)


@login_required
@role_required('super_admin', 'admin', 'principal')
def user_detail(request, user_id):
    """View user details and manage roles"""
    user = get_object_or_404(User, pk=user_id)
    user_roles = user.user_roles.all()
    available_roles = Role.objects.filter(is_active=True)
    
    context = {
        'user': user,
        'user_roles': user_roles,
        'available_roles': available_roles,
    }
    return render(request, 'accounts/user_detail.html', context)


@login_required
@role_required('super_admin', 'admin', 'principal')
def add_user_role(request, user_id):
    """Add a role to a user"""
    if request.method == 'POST':
        user = get_object_or_404(User, pk=user_id)
        role_id = request.POST.get('role_id')
        role = get_object_or_404(Role, pk=role_id, is_active=True)
        
        # Check if role already assigned
        if user.user_roles.filter(role=role).exists():
            messages.warning(request, f'User already has role: {role.display_name}')
        else:
            UserRole.objects.create(
                user=user,
                role=role,
                assigned_by=request.user
            )
            messages.success(request, f'Role {role.display_name} added to {user.username}')
    
    return redirect('user_detail', user_id=user_id)


@login_required
@role_required('super_admin', 'admin', 'principal')
def remove_user_role(request, user_id, role_id):
    """Remove a role from a user"""
    if request.method == 'POST':
        user = get_object_or_404(User, pk=user_id)
        role = get_object_or_404(Role, pk=role_id)
        
        user_role = get_object_or_404(UserRole, user=user, role=role)
        role_display_name = role.display_name
        user_role.delete()
        
        messages.success(request, f'Role {role_display_name} removed from {user.username}')
    
    return redirect('user_detail', user_id=user_id)


@login_required
@role_required('super_admin', 'admin', 'principal')
def role_list(request):
    """List all roles"""
    roles = Role.objects.all()
    
    # Filter by active status
    status_filter = request.GET.get('status', 'all')
    if status_filter == 'active':
        roles = roles.filter(is_active=True)
    elif status_filter == 'inactive':
        roles = roles.filter(is_active=False)
    
    context = {
        'roles': roles,
        'status_filter': status_filter,
    }
    return render(request, 'accounts/role_list.html', context)


@login_required
@role_required('super_admin', 'admin')
def role_detail(request, role_id):
    """View role details and manage permissions"""
    role = get_object_or_404(Role, pk=role_id)
    assigned_users = role.user_assignments.select_related('user').all()
    
    context = {
        'role': role,
        'assigned_users': assigned_users,
    }
    return render(request, 'accounts/role_detail.html', context)


@login_required
def profile(request):
    """View user's own profile"""
    user_profile = request.user.profile
    
    context = {
        'profile': user_profile,
        'roles': user_profile.get_role_display_names(),
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def edit_profile(request):
    """Edit user's own profile"""
    user_profile = request.user.profile
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=user_profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=user_profile)
    
    context = {
        'profile': user_profile,
        'form': form,
    }
    return render(request, 'accounts/edit_profile.html', context)
