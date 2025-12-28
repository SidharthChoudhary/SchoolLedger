"""
Production Settings for PythonAnywhere Deployment
This file contains settings needed for PythonAnywhere hosting
"""

from schoolapp.settings import *

# Production overrides
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'dpstibariyan$schoolledger',
        'USER': 'dpstibariyan',
        'PASSWORD': 'schoolledger@2025',  # Set this after MySQL is created
        'HOST': 'dpstibariyan.mysql.pythonanywhere-services.com',
        'PORT': '3306',
    }
}

STATIC_ROOT = '/home/dpstibariyan/SchoolLedger/static'
STATIC_URL = '/static/'

MEDIA_ROOT = '/home/dpstibariyan/SchoolLedger/media'
MEDIA_URL = '/media/'

DEBUG = False
ALLOWED_HOSTS = [
    'dpstibariyan.pythonanywhere.com',
    'localhost',
    '127.0.0.1',
]

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'  # Optional
EMAIL_HOST_PASSWORD = 'your-app-password'  # Optional

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'ERROR',
            'class': 'logging.FileHandler',
            'filename': '/home/dpstibariyan/SchoolLedger/error.log',
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
