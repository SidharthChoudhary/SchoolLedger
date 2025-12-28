# PythonAnywhere Deployment Checklist for dpstibariyan

## Account Details
- **Username:** dpstibariyan
- **Domain:** dpstibariyan.pythonanywhere.com
- **Free Tier Account**

---

## STEP 1: Prepare for GitHub Upload (Do this locally)

```bash
cd c:\LocalFolder\SchoolLedger

# Check if git is initialized
git status

# If not initialized, initialize git
git init
git add .
git commit -m "Initial commit - School Ledger with RBAC"

# Create repository on GitHub
# Then set remote:
git remote add origin https://github.com/YOUR-USERNAME/SchoolLedger.git
git branch -M main
git push -u origin main
```

**Note:** Replace YOUR-USERNAME with your GitHub username

---

## STEP 2: Login to PythonAnywhere & Create Database

1. Go to https://www.pythonanywhere.com and login
   - Username: dpstibariyan
   - Password: Dps@2025

2. Go to **"Databases"** tab
   - Click **"Create a new database"**
   - Choose **MySQL**
   - Save the password shown (you'll need it)
   - Note the connection details:
     ```
     Database: dpstibariyan$schoolledger
     Username: dpstibariyan
     Password: [SAVE THIS!]
     Host: dpstibariyan.mysql.pythonanywhere-services.com
     ```

---

## STEP 3: Clone Project in PythonAnywhere

1. Go to **"Consoles"** → **"Bash"**
2. Run these commands:

```bash
# Clone your GitHub repository
cd ~
git clone https://github.com/YOUR-USERNAME/SchoolLedger.git
cd SchoolLedger

# Create virtual environment (Python 3.10)
mkvirtualenv --python=/usr/bin/python3.10 SchoolLedger

# Install dependencies
pip install -r requirements.txt
pip install mysqlclient
pip install gunicorn
```

---

## STEP 4: Update Settings for Production

1. Still in Bash, update the production settings:

```bash
cd ~/SchoolLedger

# Edit settings.py to use MySQL
nano schoolapp/settings.py
```

2. Find this line:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

3. Replace with (from production_settings.py):
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'dpstibariyan$schoolledger',
        'USER': 'dpstibariyan',
        'PASSWORD': 'YOUR_DB_PASSWORD_HERE',  # Paste the password from Step 2
        'HOST': 'dpstibariyan.mysql.pythonanywhere-services.com',
    }
}
```

4. Also add at the end of settings.py:
```python
# Production Settings
DEBUG = False
ALLOWED_HOSTS = ['dpstibariyan.pythonanywhere.com', 'localhost']

STATIC_ROOT = '/home/dpstibariyan/SchoolLedger/static'
STATIC_URL = '/static/'

MEDIA_ROOT = '/home/dpstibariyan/SchoolLedger/media'
MEDIA_URL = '/media/'

SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

5. Save file:
   - Press: `Ctrl + O` → `Enter` → `Ctrl + X`

---

## STEP 5: Run Migrations

In Bash console (make sure virtual environment is active):

```bash
cd ~/SchoolLedger

# Activate virtual environment
workon SchoolLedger

# Run migrations
python manage.py migrate

# Initialize roles and permissions
python manage.py init_roles

# Create superuser (admin account)
python manage.py createsuperuser
# Enter:
# Username: admin
# Email: admin@school.local
# Password: [create secure password]
# Confirm Password: [same password]

# Collect static files
python manage.py collectstatic --noinput
```

---

## STEP 6: Configure Web App in PythonAnywhere

1. Go to **"Web"** tab
2. Click **"Add a new web app"**
3. Choose:
   - Domain: `dpstibariyan.pythonanywhere.com`
   - Framework: **Django**
   - Python version: **3.10**

4. After creation, scroll down and edit **WSGI configuration file**
   - Click on the blue WSGI file path
   - Delete everything and paste:

```python
import os
import sys
from pathlib import Path

path = '/home/dpstibariyan/SchoolLedger'
if path not in sys.path:
    sys.path.append(path)

os.environ['DJANGO_SETTINGS_MODULE'] = 'schoolapp.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

5. Click **"Save"**

---

## STEP 7: Configure Static & Media Files

1. Still in **"Web"** tab
2. Scroll down to **"Static files"** section
3. Add two mappings:

| URL | Directory |
|-----|-----------|
| /static/ | /home/dpstibariyan/SchoolLedger/static |
| /media/ | /home/dpstibariyan/SchoolLedger/media |

---

## STEP 8: Reload Web App

1. In **"Web"** tab
2. Look for green **"Reload dpstibariyan.pythonanywhere.com"** button
3. Click it
4. Wait 30 seconds for restart

---

## STEP 9: Test Your App

Visit these URLs in your browser:

- **Home:** https://dpstibariyan.pythonanywhere.com
- **Login:** https://dpstibariyan.pythonanywhere.com/accounts/login
  - Username: admin
  - Password: [whatever you set in Step 5]
- **Admin:** https://dpstibariyan.pythonanywhere.com/admin
- **User Management:** https://dpstibariyan.pythonanywhere.com/accounts/users

---

## STEP 10: Fix Common Issues

### If you see "ModuleNotFoundError"
```bash
workon SchoolLedger
pip install -r requirements.txt
```

### If database connection fails
- Check password in settings.py matches the one from "Databases" tab
- Verify database exists in "Databases" tab

### If static files not loading
```bash
python manage.py collectstatic --clear --noinput
```

### Check error logs
1. Go to **"Web"** tab
2. Click **"Error log"** link at bottom
3. Or in Bash:
```bash
tail -50 /var/log/dpstibariyan.pythonanywhere_com_error_log
```

---

## STEP 11: (Optional) Upgrade to Paid Plan

If you want better performance:
- Free tier: Limited resources
- **Hacker Plan ($5/month):** Recommended for school
  - Unlimited web apps
  - Better performance
  - Custom domains

Click **"Account"** → upgrade

---

## Final Checklist

- [ ] GitHub repository created with code
- [ ] PythonAnywhere account created
- [ ] MySQL database created
- [ ] Code cloned to PythonAnywhere
- [ ] Virtual environment created
- [ ] Dependencies installed
- [ ] settings.py updated with database credentials
- [ ] Migrations run successfully
- [ ] Roles initialized (init_roles)
- [ ] Superuser created
- [ ] Static files collected
- [ ] Web app configured
- [ ] WSGI file updated
- [ ] Static/Media paths configured
- [ ] App reloaded
- [ ] Tested home page
- [ ] Tested login page
- [ ] Tested admin panel

---

## Live Application URLs

- **Main App:** https://dpstibariyan.pythonanywhere.com
- **Login:** https://dpstibariyan.pythonanywhere.com/accounts/login
- **Admin:** https://dpstibariyan.pythonanywhere.com/admin
- **User Management:** https://dpstibariyan.pythonanywhere.com/accounts/users

---

## Support

If you get stuck:
1. Check PythonAnywhere error log
2. Review step-by-step guide
3. Contact PythonAnywhere support: help@pythonanywhere.com

---

## Next Steps After Deployment

1. Create additional user accounts for staff
2. Assign roles to users (Accountant, Teacher, etc.)
3. Start using the system
4. Configure email (optional)
5. Monitor usage and performance
6. Plan for upgrading if needed

---

Good luck! Your School Ledger will be live soon! 🚀
