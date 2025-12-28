import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
django.setup()

from django.test import RequestFactory
from dailyLedger.views import heads_home

# Create a mock request
factory = RequestFactory()
request = factory.get('/ledger-expense/heads/')

# Get the response
response = heads_home(request)

# Get the context
if hasattr(response, 'context_data'):
    print("head_data_json sample:")
    data = response.context_data.get('head_data_json', '')
    print(f"Type: {type(data)}")
    print(f"Length: {len(data)}")
    print(f"First 300 chars: {data[:300]}")
