import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'schoolapp.settings')
django.setup()

from dailyLedger.models import Head

count = Head.objects.count()
print(f"Total Head records: {count}")
if count > 0:
    print("Sample records:")
    for h in Head.objects.all()[:5]:
        print(f"  {h.ledger_type} - {h.major_head} - {h.head} - {h.sub_head}")
else:
    print("Head table is empty! Need to import data from CSV.")
