"""
URL configuration for schoolapp project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from dailyLedger.views import (
    income_home, delete_income,
    api_get_classes, api_get_students, api_get_student_srn, api_get_fee_account,
    bulk_import_ledger, download_ledger_template
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("website.urls")),
    path("ledger-expense/", include("dailyLedger.urls")),
    # API endpoints must come before the catch-all income_home path
    path("ledger-income/api/classes/<int:session_id>/", api_get_classes, name="api_get_classes"),
    path("ledger-income/api/students/<int:session_id>/<int:class_id>/", api_get_students, name="api_get_students"),
    path("ledger-income/api/student-srn/<int:student_id>/", api_get_student_srn, name="api_get_student_srn"),
    path("ledger-income/api/fee-account/<str:srn>/", api_get_fee_account, name="api_get_fee_account"),
    path("ledger-income/bulk-import-ledger/", bulk_import_ledger, name="income_bulk_import_ledger"),
    path("ledger-income/download-ledger-template/", download_ledger_template, name="income_download_ledger_template"),
    # General income routes
    path("ledger-income/", income_home, name="income_home"),
    path("ledger-income/delete/<int:pk>/", delete_income, name="delete_income"),
    path("employees/", include("employees.urls")),
    path("students/", include("students.urls")),
]



urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
