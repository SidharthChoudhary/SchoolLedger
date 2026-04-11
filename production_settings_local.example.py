"""Copy this file to production_settings_local.py on the server.

That local file is gitignored, so deploys will not overwrite it.
"""

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'dpstibariyan$schoolledger',
        'USER': 'dpstibariyan',
        'PASSWORD': 'replace-with-your-pythonanywhere-db-password',
        'HOST': 'dpstibariyan.mysql.pythonanywhere-services.com',
        'PORT': '3306',
        'OPTIONS': {
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

ALLOWED_HOSTS = [
    'dpstibariyan.pythonanywhere.com',
    'www.dpstibariyan.pythonanywhere.com',
    'localhost',
    '127.0.0.1',
]

STATIC_ROOT = '/home/dpstibariyan/SchoolLedger/static'
MEDIA_ROOT = '/home/dpstibariyan/SchoolLedger/media'

EMAIL_HOST_USER = ''
EMAIL_HOST_PASSWORD = ''
