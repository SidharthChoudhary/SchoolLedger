#!/usr/bin/env python
import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
django.setup()

from django.test import Client

client = Client()
response = client.get('/ledger-income/api/classes/1/')
print(f"Status: {response.status_code}")
print(f"Content-Type: {response.get('Content-Type')}")
print(f"Content: {response.content.decode()}")
