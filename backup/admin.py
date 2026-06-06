import json
import os
import tempfile
from datetime import datetime, date
from io import StringIO

from django.apps import apps
from django.contrib import admin, messages
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import connection, transaction
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import path

from .models import DatabaseBackup

# ---------------------------------------------------------------------------
# Tables exported/imported in strict dependency order.
# Restore uses the same list; clear uses the reverse.
# ---------------------------------------------------------------------------
BACKUP_MODELS = [
    # Django internals
    'contenttypes.contenttype',
    'auth.permission',
    'auth.group',
    'auth.user',
    # Core reference data (no FKs)
    'dailyLedger.session',
    'students.class',
    'employees.employee',
    'dailyLedger.head',
    'students.feesaccount',
    'accounts.role',
    # User-linked tables
    'accounts.userrole',
    'accounts.userprofile',
    # Tables that depend on session + reference data
    'students.feesaccountagreement',
    'dailyLedger.feesstructure',
    'dailyLedger.expense',
    'employees.employeeattendance',
    'employees.employeepayrollentry',
    # Student depends on class, feesaccount, session
    'students.student',
    # Tables that depend on student
    'dailyLedger.income',
    'students.studentaccount',
    'students.sessionclassstudentmap',
    'students.studentattendance',
]

# ---------------------------------------------------------------------------
# M2M through-tables and Django internal tables that are NOT in BACKUP_MODELS
# but hold FK references to tables we delete. These must be cleared FIRST so
# that the main deletions don't hit FK constraint violations (especially on
# SQLite where disabling FK checks inside a transaction is not possible).
# ---------------------------------------------------------------------------
PRE_CLEAR_TABLES = [
    'django_admin_log',            # FK → auth_user, contenttypes
    'auth_user_groups',            # M2M: auth.user ↔ auth.group
    'auth_user_user_permissions',  # M2M: auth.user ↔ auth.permission
    'auth_group_permissions',      # M2M: auth.group ↔ auth.permission
    'accounts_role_permissions',   # M2M: accounts.role ↔ auth.permission
]


@admin.register(DatabaseBackup)
class DatabaseBackupAdmin(admin.ModelAdmin):

    # ------------------------------------------------------------------
    # Permission guards – superuser only
    # ------------------------------------------------------------------
    def has_module_perms(self, request, app_label=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    # ------------------------------------------------------------------
    # URL routing
    # ------------------------------------------------------------------
    def get_urls(self):
        custom_urls = [
            path(
                'create/',
                self.admin_site.admin_view(self.create_backup_view),
                name='backup_create',
            ),
            path(
                'restore/',
                self.admin_site.admin_view(self.restore_backup_view),
                name='backup_restore',
            ),
            path(
                'export-monthly/',
                self.admin_site.admin_view(self.export_monthly_view),
                name='backup_export_monthly',
            ),
        ]
        return custom_urls + super().get_urls()

    # ------------------------------------------------------------------
    # Main page (changelist)
    # ------------------------------------------------------------------
    def changelist_view(self, request, extra_context=None):
        from dailyLedger.models import Session as AcademicSession
        sessions = AcademicSession.objects.order_by('-session').values_list('session', flat=True)
        context = {
            **self.admin_site.each_context(request),
            'title': 'Database Backup & Restore',
            'opts': self.model._meta,
            'export_sessions': list(sessions),
        }
        return render(request, 'admin/backup/backup_restore.html', context)

    # ------------------------------------------------------------------
    # Create backup → stream JSON download
    # ------------------------------------------------------------------
    def create_backup_view(self, request):
        if request.method != 'POST':
            return HttpResponseRedirect('../')
        if not request.user.is_superuser:
            messages.error(request, 'Only superusers can create backups.')
            return HttpResponseRedirect('../')

        try:
            buf = StringIO()
            call_command(
                'dumpdata',
                *BACKUP_MODELS,
                indent=2,
                stdout=buf,
                natural_foreign=True,
                natural_primary=False,
            )
            json_data = buf.getvalue()

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'schoolledger_backup_{timestamp}.json'
            response = HttpResponse(json_data, content_type='application/json')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except Exception as exc:
            messages.error(request, f'Backup failed: {exc}')
            return HttpResponseRedirect('../')

    # ------------------------------------------------------------------
    # Restore backup ← uploaded JSON file
    # ------------------------------------------------------------------
    def restore_backup_view(self, request):
        if request.method != 'POST':
            return HttpResponseRedirect('../')
        if not request.user.is_superuser:
            messages.error(request, 'Only superusers can restore backups.')
            return HttpResponseRedirect('../')

        # Require typed confirmation
        if request.POST.get('confirm_restore', '').strip() != 'RESTORE':
            messages.error(
                request,
                'Restore cancelled: you must type RESTORE in the confirmation field.',
            )
            return HttpResponseRedirect('../')

        if 'backup_file' not in request.FILES:
            messages.error(request, 'No backup file was uploaded.')
            return HttpResponseRedirect('../')

        backup_file = request.FILES['backup_file']

        # Validate JSON before touching the database
        try:
            content = backup_file.read().decode('utf-8')
            json.loads(content)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            messages.error(request, f'Invalid backup file: {exc}')
            return HttpResponseRedirect('../')

        tmp_path = None
        try:
            # Write to a temp file so loaddata can read it
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.json', delete=False, encoding='utf-8'
            ) as tmp:
                tmp.write(content)
                tmp_path = tmp.name

            # For MySQL: disable FK checks at session level (outside the
            # transaction so it applies to the whole operation).
            # For SQLite: PRAGMA can't be set inside a transaction, so instead
            # we pre-clear M2M/internal tables in the correct order to avoid
            # FK violations without needing to disable checks at all.
            if connection.vendor == 'mysql':
                with connection.cursor() as cur:
                    cur.execute('SET FOREIGN_KEY_CHECKS = 0')

            try:
                with transaction.atomic():
                    q = connection.ops.quote_name  # DB-appropriate identifier quoting

                    # Step 1: clear M2M through-tables and Django internal
                    # tables that have FKs pointing at tables we're about to
                    # delete.  Must happen BEFORE the main deletion loop.
                    with connection.cursor() as cur:
                        for table in PRE_CLEAR_TABLES:
                            try:
                                cur.execute(f'DELETE FROM {q(table)}')
                            except Exception:
                                pass  # table may not exist in all environments

                    # Step 2: clear every app table in reverse dependency order
                    with connection.cursor() as cur:
                        for model_label in reversed(BACKUP_MODELS):
                            app_label, model_name = model_label.split('.')
                            try:
                                model = apps.get_model(app_label, model_name)
                                cur.execute(
                                    f'DELETE FROM {q(model._meta.db_table)}'
                                )
                            except LookupError:
                                pass

                    # Step 3: restore from fixture.
                    # Disconnect the User post_save signal handlers that
                    # auto-create UserProfile, otherwise loaddata triggers
                    # the signal when inserting auth.user → creates a
                    # UserProfile row → then the fixture's own UserProfile
                    # insert fails with a UNIQUE constraint violation.
                    from django.db.models.signals import post_save
                    from django.contrib.auth.models import User as AuthUser
                    from accounts.signals import (
                        create_user_profile,
                        save_user_profile,
                    )
                    post_save.disconnect(create_user_profile, sender=AuthUser)
                    post_save.disconnect(save_user_profile, sender=AuthUser)
                    try:
                        call_command(
                            'loaddata', tmp_path,
                            verbosity=0,
                            ignorenonexistent=True,
                        )
                    finally:
                        post_save.connect(create_user_profile, sender=AuthUser)
                        post_save.connect(save_user_profile, sender=AuthUser)

                # Clear Django's ContentType cache so it picks up fresh data
                ContentType.objects.clear_cache()
                messages.success(
                    request,
                    'Database restored successfully from backup. '
                    'Please log in again.',
                )

            finally:
                if connection.vendor == 'mysql':
                    with connection.cursor() as cur:
                        cur.execute('SET FOREIGN_KEY_CHECKS = 1')

        except Exception as exc:
            messages.error(request, f'Restore failed: {exc}')

        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

        return HttpResponseRedirect('../')

    # ------------------------------------------------------------------
    # Monthly CSV export → ZIP download
    # ------------------------------------------------------------------
    def export_monthly_view(self, request):
        if request.method != 'POST':
            return HttpResponseRedirect('../')
        if not request.user.is_superuser:
            messages.error(request, 'Only superusers can export reports.')
            return HttpResponseRedirect('../')

        try:
            session_str = request.POST.get('export_session', '').strip()
            month       = int(request.POST.get('export_month', -1))
        except (ValueError, TypeError):
            messages.error(request, 'Invalid month.')
            return HttpResponseRedirect('../')

        from .management.commands.export_monthly_report import (
            build_session_zip, build_month_zip, _valid_session, MONTH_NAMES,
        )

        if not session_str:
            messages.error(request, 'Please select a session.')
            return HttpResponseRedirect('../')
        if not _valid_session(session_str):
            messages.error(request, f'Invalid session: "{session_str}".')
            return HttpResponseRedirect('../')
        if not (0 <= month <= 12):
            messages.error(request, 'Please select a month.')
            return HttpResponseRedirect('../')

        try:
            if month == 0:
                zip_bytes = build_session_zip(session_str)
                filename  = f'schoolledger_{session_str}_all_months.zip'
            else:
                zip_bytes = build_month_zip(session_str, month)
                filename  = f'schoolledger_{session_str}_{month:02d}_{MONTH_NAMES[month]}.zip'
            response = HttpResponse(zip_bytes, content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response

        except Exception as exc:
            messages.error(request, f'Export failed: {exc}')
            return HttpResponseRedirect('../')
