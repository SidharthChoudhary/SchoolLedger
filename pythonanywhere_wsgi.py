# ============================================================================
# This is the WSGI configuration file for PythonAnywhere
# Copy this content into your WSGI file on PythonAnywhere:
# /var/www/dpstibariyan_pythonanywhere_com_wsgi.py
# ============================================================================

import os
import sys

# Add your project directory to Python path
path = '/home/dpstibariyan/SchoolLedger'
if path not in sys.path:
    sys.path.append(path)

# Set Django settings module
os.environ['DJANGO_SETTINGS_MODULE'] = 'schoolapp.settings'

# Setup Django
import django
django.setup()

# Get the WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
