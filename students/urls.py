from django.urls import path
from . import views

urlpatterns = [
    # Student URLs
    path('add/', views.add_student, name='add_student'),
    path('confirm-fee-account/', views.confirm_fee_account_link, name='confirm_fee_account_link'),
    path('confirm-student-addition/', views.confirm_student_addition, name='confirm_student_addition'),
    path('view/', views.view_students, name='view_students'),
    path('details/<int:pk>/', views.student_details, name='student_details'),
    path('edit/<int:pk>/', views.edit_student, name='edit_student'),
    path('delete/<int:pk>/', views.delete_student, name='delete_student'),
    path('account/', views.select_student_for_account, name='select_student_account'),
    path('account/<int:student_id>/', views.student_account_detail, name='student_account_detail'),
    path('year/', views.student_year_view, name='student_year_view'),
    path('attendance/', views.student_attendance_classes, name='student_attendance_classes'),
    path('attendance/class/<int:class_id>/', views.student_attendance_register, name='student_attendance_register'),
    path('attendance-records/', views.student_attendance_records, name='student_attendance_records'),
    
    # Class URLs
    path('classes/', views.view_classes, name='view_classes'),
    path('classes/add/', views.add_class, name='add_class'),
    path('classes/edit/<int:pk>/', views.edit_class, name='edit_class'),
    path('classes/delete/<int:pk>/', views.delete_class, name='delete_class'),
    
    # Fees Account URLs
    path('fees-account/', views.view_fees_accounts, name='view_fees_accounts'),
    path('fees-account/add/', views.add_fees_account, name='add_fees_account'),
    path('fees-account/edit/<int:pk>/', views.edit_fees_account, name='edit_fees_account'),
    path('fees-account/delete/<int:pk>/', views.delete_fees_account, name='delete_fees_account'),
    path('link-fee-account/', views.link_fee_account, name='link_fee_account'),
    
    # Session Class Student Map URLs
    path('manage-session-class-student-map/', views.manage_session_class_student_map, name='manage_session_class_student_map'),
    path('get-next-class/<int:class_id>/', views.get_next_class, name='get_next_class'),
    path('manage-session-class-student-map/delete/<int:mapping_id>/', views.delete_session_class_student_map, name='delete_session_class_student_map'),
    path('promote-session/', views.promote_session_page, name='promote_session_page'),
]
