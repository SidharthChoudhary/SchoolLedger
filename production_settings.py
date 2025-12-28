"""
Production Settings for PythonAnywhere Deployment
This file contains settings needed for PythonAnywhere hosting
"""

# Production Database Configuration
# Replace with your actual database credentials from PythonAnywhere
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'dpstibariyan$schoolledger',
        'USER': 'dpstibariyan',
        'PASSWORD': 'YOUR_DB_PASSWORD_HERE',  # Set this after MySQL is created
        'HOST': 'dpstibariyan.mysql.pythonanywhere-services.com',
        'PORT': '3306',
    }
}

# Static files (CSS, JavaScript, Images)
STATIC_ROOT = '/home/dpstibariyan/SchoolLedger/static'
STATIC_URL = '/static/'

# Media files (User uploads)
MEDIA_ROOT = '/home/dpstibariyan/SchoolLedger/media'
MEDIA_URL = '/media/'

# Debug and allowed hosts
DEBUG = False
ALLOWED_HOSTS = [
    'dpstibariyan.pythonanywhere.com',
    'localhost',
    '127.0.0.1',
]

# Security Settings
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Email Configuration (Optional - for notifications)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'  # Optional
EMAIL_HOST_PASSWORD = 'your-app-password'  # Optional

# Logging
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
