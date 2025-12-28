from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Authentication
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    
    # User Management
    path('users/', views.user_list, name='user_list'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('users/<int:user_id>/roles/add/', views.add_user_role, name='add_user_role'),
    path('users/<int:user_id>/roles/<int:role_id>/remove/', views.remove_user_role, name='remove_user_role'),
    
    # Role Management
    path('roles/', views.role_list, name='role_list'),
    path('roles/<int:role_id>/', views.role_detail, name='role_detail'),
    
    # Profile Management
    path('profile/', views.profile, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
]
