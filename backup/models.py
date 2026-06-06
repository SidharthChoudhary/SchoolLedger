from django.db import models


class DatabaseBackup(models.Model):
    """
    Proxy/unmanaged model used solely to attach a custom admin page.
    No database table is created for this model.
    """

    class Meta:
        managed = False
        verbose_name = 'Database Backup & Restore'
        verbose_name_plural = 'Database Backup & Restore'
        default_permissions = ()
        app_label = 'backup'
