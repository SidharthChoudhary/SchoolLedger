# PythonAnywhere Deployment Guide for School Ledger

## Step 1: Prepare Your Application for Deployment

### 1.1 Update settings.py for Production

First, let me create the production settings:
```python
# schoolapp/settings.py - Add at the end

# Production Settings
DEBUG = False
ALLOWED_HOSTS = ['yourusername.pythonanywhere.com', 'your-domain.com']

# Database - We'll configure this in PythonAnywhere
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'yourusername$schoolledger',
        'USER': 'yourusername',
        'PASSWORD': 'your-db-password',
        'HOST': 'yourusername.mysql.pythonanywhere-services.com',
        'PORT': '3306',
    }
}

# Static Files
STATIC_ROOT = '/home/yourusername/SchoolLedger/static/'
STATIC_URL = '/static/'

# Media Files
MEDIA_ROOT = '/home/yourusername/SchoolLedger/media/'
MEDIA_URL = '/media/'

# Security
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Email Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
```

### 1.2 Create requirements.txt

Run this command locally:
```bash
pip freeze > requirements.txt
```

Or manually create with essential packages:
```
Django==6.0
Pillow==11.0.0
mysqlclient==2.2.0
psycopg2-binary==2.9.9
python-decouple==3.8
gunicorn==21.2.0
```

### 1.3 Create .gitignore

```
*.pyc
__pycache__/
*.sqlite3
*.db
.env
/venv/
/media/
/static/
.DS_Store
*.log
```

---

## Step 2: Create PythonAnywhere Account

1. Go to https://www.pythonanywhere.com
2. Click **"Sign Up"** (Beginner account is free)
3. Choose username (this will be your domain: `yourusername.pythonanywhere.com`)
4. Verify email
5. Login to dashboard

---

## Step 3: Upload Code to PythonAnywhere

### Option A: Using Git (Recommended)

1. **Push code to GitHub first:**
```bash
cd c:\LocalFolder\SchoolLedger
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/SchoolLedger.git
git branch -M main
git push -u origin main
```

2. **In PythonAnywhere dashboard:**
   - Open **"Consoles"** → **"Bash"**
   - Run:
```bash
cd ~
git clone https://github.com/yourusername/SchoolLedger.git
cd SchoolLedger
```

### Option B: Manual Upload

1. In PythonAnywhere, go to **"Files"**
2. Click **"Upload a file"**
3. Upload your entire project folder

---

## Step 4: Set Up Virtual Environment

1. Open **"Consoles"** → **"Bash"**

```bash
# Create virtual environment
mkvirtualenv --python=/usr/bin/python3.10 SchoolLedger

# Install dependencies
pip install -r requirements.txt
pip install gunicorn
pip install mysqlclient
```

---

## Step 5: Configure Web App

1. Go to **"Web"** tab in PythonAnywhere
2. Click **"Add a new web app"**
3. Choose:
   - Domain: `yourusername.pythonanywhere.com`
   - Framework: **Django**
   - Python version: **3.10**

4. **Edit WSGI configuration file:**
   - Click on the WSGI file link (should be `/var/www/yourusername_pythonanywhere_com_wsgi.py`)
   - Replace with:

```python
import os
import sys
from pathlib import Path

# Add your project to the path
path = '/home/yourusername/SchoolLedger'
if path not in sys.path:
    sys.path.append(path)

# Set Django settings module
os.environ['DJANGO_SETTINGS_MODULE'] = 'schoolapp.settings'

# Import Django
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

---

## Step 6: Configure Database

### Create MySQL Database in PythonAnywhere

1. Go to **"Databases"** tab
2. Click **"Create a new database"**
3. Choose **MySQL**
4. Note your credentials:
   - Database name: `yourusername$schoolledger`
   - Username: `yourusername`
   - Password: (auto-generated)

### Update settings.py with Database Credentials

Replace in `schoolapp/settings.py`:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'yourusername$schoolledger',
        'USER': 'yourusername',
        'PASSWORD': 'your-db-password-from-databases-tab',
        'HOST': 'yourusername.mysql.pythonanywhere-services.com',
    }
}
```

---

## Step 7: Run Migrations

1. Open **"Consoles"** → **"Bash"**
2. Activate virtual environment:
```bash
workon SchoolLedger
cd /home/yourusername/SchoolLedger
```

3. Run migrations:
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py init_roles
```

4. Create superuser:
```bash
python manage.py createsuperuser
# Enter:
# Username: admin
# Email: your-email@school.local
# Password: secure-password
```

5. Collect static files:
```bash
python manage.py collectstatic --noinput
```

---

## Step 8: Configure Static & Media Files

1. In **"Web"** tab, scroll to **"Static files"** section
2. Add mapping:

| URL path | Directory |
|----------|-----------|
| /static/ | /home/yourusername/SchoolLedger/static |
| /media/ | /home/yourusername/SchoolLedger/media |

---

## Step 9: Reload Web App

1. Go to **"Web"** tab
2. Click green **"Reload yourusername.pythonanywhere.com"** button
3. Wait 30 seconds for restart

---

## Step 10: Test Your App

1. Visit: `https://yourusername.pythonanywhere.com`
2. Should see your School Ledger homepage
3. Login page: `https://yourusername.pythonanywhere.com/accounts/login/`
4. Admin: `https://yourusername.pythonanywhere.com/admin/`

---

## Troubleshooting

### Error: "ModuleNotFoundError"
```bash
workon SchoolLedger
pip install -r requirements.txt
```

### Error: "Database connection refused"
- Check database credentials in settings.py
- Verify database exists in PythonAnywhere "Databases" tab

### Static files not loading
```bash
python manage.py collectstatic --noinput --clear
```

### Debug mode to check errors
Temporarily in settings.py:
```python
DEBUG = True
```
Reload and check browser. Remember to set `DEBUG = False` after fixing.

### View Error Logs
- PythonAnywhere → Web → Error log
- Or: Cat error log in Bash:
```bash
cat /var/log/yourusername.pythonanywhere_com_error_log
```

---

## Security Checklist Before Production

- [ ] Set `DEBUG = False`
- [ ] Generate new `SECRET_KEY`
- [ ] Set strong database password
- [ ] Configure ALLOWED_HOSTS
- [ ] Enable SSL (HTTPS)
- [ ] Set secure cookie flags
- [ ] Disable DEBUG_PROPAGATE_EXCEPTIONS
- [ ] Configure email backend
- [ ] Backup database regularly
- [ ] Monitor error logs

---

## Custom Domain Setup (Optional)

1. Buy domain (Godaddy, Namecheap, etc.)
2. In **"Web"** tab → **"Add a domain"**
3. Set DNS records to PythonAnywhere IP:
   ```
   A Record: 188.166.xxx.xxx
   ```
4. Update ALLOWED_HOSTS in settings.py:
   ```python
   ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']
   ```
5. Reload app

---

## Next Steps

1. Configure email for notifications
2. Set up automated backups
3. Monitor usage/logs regularly
4. Plan for scaling if needed
5. Set up SSL certificate (PythonAnywhere auto-renews)

---

## Useful Commands in PythonAnywhere Bash

```bash
# Activate virtual environment
workon SchoolLedger

# Check Python version
python --version

# List installed packages
pip list

# View app logs
tail -f /var/log/yourusername.pythonanywhere_com_error_log

# Check disk usage
du -sh /home/yourusername/

# Database operations
python manage.py dbshell
```

---

## Pricing

- **Free Tier:** Basic hosting, limited resources
- **Hacker Plan:** $5/month - Unlimited web apps, better performance
- **Professional Plan:** $20+/month - Custom domain, more power

For a school system, **Hacker Plan ($5/month)** is recommended.

---

## Support

- **PythonAnywhere Help:** https://help.pythonanywhere.com/
- **Django Help:** https://docs.djangoproject.com/
- **Contact Support:** help@pythonanywhere.com

Good luck with your deployment! 🚀
