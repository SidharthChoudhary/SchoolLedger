"""Production settings wrapper for hosted deployments.

This file is safe to commit. Put server-only values in
production_settings_local.py, which is gitignored and survives git pulls.
"""

import os

from schoolapp.settings import *


def _split_csv(value):
    return [item.strip() for item in value.split(',') if item.strip()]


DEBUG = False

ALLOWED_HOSTS = _split_csv(
    os.environ.get(
        'DJANGO_ALLOWED_HOSTS',
        'dpstibariyan.pythonanywhere.com,localhost,127.0.0.1',
    )
)

STATIC_ROOT = os.environ.get('DJANGO_STATIC_ROOT', '/home/dpstibariyan/SchoolLedger/static')
STATIC_URL = '/static/'

MEDIA_ROOT = os.environ.get('DJANGO_MEDIA_ROOT', '/home/dpstibariyan/SchoolLedger/media')
MEDIA_URL = '/media/'

DATABASES = {
    'default': {
        'ENGINE': os.environ.get('DJANGO_DB_ENGINE', 'django.db.backends.mysql'),
        'NAME': os.environ.get('DJANGO_DB_NAME', ''),
        'USER': os.environ.get('DJANGO_DB_USER', ''),
        'PASSWORD': os.environ.get('DJANGO_DB_PASSWORD', ''),
        'HOST': os.environ.get('DJANGO_DB_HOST', ''),
        'PORT': os.environ.get('DJANGO_DB_PORT', '3306'),
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('DJANGO_EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('DJANGO_EMAIL_HOST_PASSWORD', '')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': os.environ.get('DJANGO_ERROR_LOG', '/home/dpstibariyan/SchoolLedger/error.log'),
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}

try:
    from production_settings_local import *
except ImportError:
    pass


if not DATABASES['default'].get('NAME'):
    raise RuntimeError(
        'Production database settings are missing. Create production_settings_local.py '
        'from production_settings_local.example.py or set DJANGO_DB_* environment variables.'
    )

