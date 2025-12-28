# 🚀 MANUAL STEPS FOR PYTHONANYWHERE DEPLOYMENT
# Only YOU can do these - I've automated everything else locally

## ACCOUNT CREDENTIALS
```
Username: dpstibariyan
Password: Dps@2025
Website: https://www.pythonanywhere.com
```

---

## ✅ WHAT I'VE ALREADY DONE (Automated)
- ✅ Initialized Git repository locally
- ✅ Committed all 355 project files
- ✅ Generated requirements.txt with all dependencies
- ✅ Created WSGI configuration file (pythonanywhere_wsgi.py)
- ✅ Created MySQL settings template (MYSQL_CONFIGURATION.txt)
- ✅ Created production settings reference

---

## 📋 ONLY YOU NEED TO DO THESE STEPS

### STEP 1: Create GitHub Repository & Push Code
**What this does:** Makes your code accessible from PythonAnywhere

**Steps:**
1. Go to https://github.com/new

2. Create a new repository called "SchoolLedger" (or similar)
3. **COPY the clone URL** (looks like: https://github.com/YOUR-USERNAME/SchoolLedger.git)
4. Return to your local project folder in PowerShell:
   ```powershell
   cd c:\LocalFolder\SchoolLedger
   git remote add origin https://github.com/YOUR-USERNAME/SchoolLedger.git
   git branch -M main
   git push -u origin main
   ```
5. You may need to use a GitHub Personal Access Token instead of password
   - Go to: https://github.com/settings/tokens
   - Create a token with 'repo' permissions
   - Use that token as your password when pushing

**✅ Result:** Your code is now on GitHub, ready to clone into PythonAnywhere

---

### STEP 2: Create MySQL Database in PythonAnywhere
**What this does:** Creates the database where your application data will be stored

**Steps:**
1. Login to https://www.pythonanywhere.com (dpstibariyan / Dps@2025)
2. Click "Databases" tab in top menu
3. Click "Add a new database"
4. Choose "MySQL"
5. **IMPORTANT:** Copy the password shown - you'll need it in STEP 5
   - Write it down: ___________________
6. Note these details:
   - Database Name: dpstibariyan$schoolledger
   - Username: dpstibariyan
   - Host: dpstibariyan.mysql.pythonanywhere-services.com
   - Password: [the one you just saved]

**✅ Result:** MySQL database is ready to use

---

### STEP 3: Clone Project in PythonAnywhere Bash
**What this does:** Downloads your GitHub code into PythonAnywhere server

**Steps:**
1. In PythonAnywhere, click "Consoles" tab
2. Click "Bash" to open a terminal
3. Run these commands:
   ```bash
   cd ~
   git clone https://github.com/YOUR-USERNAME/SchoolLedger.git
   cd SchoolLedger
   ```
   (Replace YOUR-USERNAME with your actual GitHub username)

4. Verify it worked:
   ```bash
   ls -la
   ```
   You should see folders: accounts, dailyLedger, employees, etc.

**✅ Result:** Code is now on PythonAnywhere server

---

### STEP 4: Create Virtual Environment & Install Dependencies
**What this does:** Sets up isolated Python environment with all required packages

**Steps:**
1. Still in Bash console, run:
   ```bash
   mkvirtualenv --python=/usr/bin/python3.10 SchoolLedger
   ```
   (Wait for it to complete - prompt should show `(SchoolLedger)`)

2. Make sure you're in the project directory:
   ```bash
   cd ~/SchoolLedger
   ```

3. Install all Python packages:
   ```bash
   pip install -r requirements.txt
   pip install mysqlclient
   pip install gunicorn
   ```
   (Wait for all to complete - you should see "Successfully installed" messages)

**✅ Result:** All Python packages are installed and ready

---

### STEP 5: Configure Database Connection in Settings
**What this does:** Tells Django how to connect to your MySQL database

**Steps:**
1. Still in Bash console, open settings file:
   ```bash
   nano schoolapp/settings.py
   ```

2. Find the DATABASES section (around line 80-90)
   - Look for: `'ENGINE': 'django.backends.sqlite3',`
   - This is the SQLite config we're replacing

3. **Replace the entire DATABASES dictionary** with this:
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.mysql',
           'NAME': 'dpstibariyan$schoolledger',
           'USER': 'dpstibariyan',
           'PASSWORD': 'YOUR_MYSQL_PASSWORD_HERE',
           'HOST': 'dpstibariyan.mysql.pythonanywhere-services.com',
           'PORT': '3306',
           'OPTIONS': {
               'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"
           }
       }
   }
   ```
   
4. **Replace 'YOUR_MYSQL_PASSWORD_HERE'** with the password you saved in STEP 2

5. Scroll to the **END of the file** and add these lines:
   ```python
   # Production Settings
   DEBUG = False
   ALLOWED_HOSTS = ['dpstibariyan.pythonanywhere.com', 'www.dpstibariyan.pythonanywhere.com']
   STATIC_ROOT = '/home/dpstibariyan/SchoolLedger/static'
   MEDIA_ROOT = '/home/dpstibariyan/SchoolLedger/media'
   
   # Security
   SECURE_SSL_REDIRECT = True
   SESSION_COOKIE_SECURE = True
   CSRF_COOKIE_SECURE = True
   SECURE_HSTS_SECONDS = 31536000
   SECURE_HSTS_INCLUDE_SUBDOMAINS = True
   SECURE_HSTS_PRELOAD = True
   USE_X_FORWARDED_HOST = True
   SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
   ```

6. Save the file:
   - Press: `Ctrl + O`
   - Press: `Enter`
   - Press: `Ctrl + X`

7. Verify it saved correctly:
   ```bash
   grep "DATABASES" schoolapp/settings.py
   ```
   You should see your MySQL config

**✅ Result:** Django now knows how to connect to your MySQL database

---

### STEP 6: Run Database Migrations & Initialize
**What this does:** Creates all database tables and sets up user roles

**Steps:**
1. Still in Bash, make sure you're in the project:
   ```bash
   cd ~/SchoolLedger
   workon SchoolLedger
   ```

2. Create database tables:
   ```bash
   python manage.py migrate
   ```
   Wait for completion. You should see messages like "Running migrations" and "OK"

3. Initialize the RBAC system (creates 6 roles):
   ```bash
   python manage.py init_roles
   ```
   You should see: "6 roles created with permissions"

4. Create admin user:
   ```bash
   python manage.py createsuperuser
   ```
   - Username: `admin`
   - Email: `admin@school.local`
   - Password: Choose a strong password (write it down!)
   - Confirm password

5. Collect static files (CSS, JavaScript, images):
   ```bash
   python manage.py collectstatic --noinput
   ```
   Wait for completion.

**✅ Result:** Database is initialized, admin user created, static files collected

---

### STEP 7: Configure Web App in PythonAnywhere
**What this does:** Tells PythonAnywhere how to run your Django application

**Steps:**
1. Go to "Web" tab in PythonAnywhere
2. Click "Add a new web app"
3. For domain, select: `dpstibariyan.pythonanywhere.com`
4. For framework, select: **Django**
5. For Python version, select: **3.10**
6. Click "Next" - it creates the web app configuration

7. **Configure the WSGI file:**
   - In the "Web" tab, you'll see a blue link to your WSGI file
   - Click it to open the WSGI configuration file
   - **Delete ALL the code** in that file
   - **Paste this code:**
   ```python
   import os
   import sys
   
   path = '/home/dpstibariyan/SchoolLedger'
   if path not in sys.path:
       sys.path.append(path)
   
   os.environ['DJANGO_SETTINGS_MODULE'] = 'schoolapp.settings'
   
   import django
   django.setup()
   
   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```
   - Click "Save"

8. **Configure Static Files:**
   - Back in the "Web" tab, scroll down to "Static files"
   - Click "Add a static files mapping"
   - For first mapping:
     - URL: `/static/`
     - Directory: `/home/dpstibariyan/SchoolLedger/static`
   - Click "Add another"
   - For second mapping:
     - URL: `/media/`
     - Directory: `/home/dpstibariyan/SchoolLedger/media`

**✅ Result:** Web app is configured and ready to run

---

### STEP 8: Start Your Application
**What this does:** Activates your web application

**Steps:**
1. Back in "Web" tab
2. Look for the green **"Reload dpstibariyan.pythonanywhere.com"** button
3. Click it
4. Wait 30 seconds for it to restart
5. You should see a green checkmark: ✓ Web app is running

**✅ Result:** Your application is now LIVE!

---

### STEP 9: Test Your Application
**What this does:** Verifies everything is working

**Test URLs:**
```
Home Page: https://dpstibariyan.pythonanywhere.com
Login: https://dpstibariyan.pythonanywhere.com/accounts/login
Admin Panel: https://dpstibariyan.pythonanywhere.com/admin
```

**Login with:**
- Username: `admin`
- Password: [the password you created in STEP 6]

**What you should see:**
- ✅ Homepage loads with school ledger branding
- ✅ Login page shows (try logging in)
- ✅ After login, you see the profile page
- ✅ Admin panel is accessible
- ✅ CSS/styling is visible (not plain HTML)
- ✅ All menu items are clickable

---

## 🆘 TROUBLESHOOTING

### If you see "Error 500"
1. Check error logs: Click "Web" → scroll down → "Error log"
2. Most common issue: Wrong MySQL password in settings.py
3. Check: Does password in settings.py match what MySQL gave you?

### If database won't connect
1. Check MySQL is actually running:
   - Go to "Databases" tab
   - Is your MySQL database listed?
2. Check the password - copy-paste to avoid typos
3. Check the hostname: `dpstibariyan.mysql.pythonanywhere-services.com`

### If static files don't load (no CSS)
1. In Bash console:
   ```bash
   python manage.py collectstatic --clear --noinput
   ```
2. Go back to "Web" tab and click "Reload"

### If you see "ModuleNotFoundError"
1. Make sure all packages installed:
   ```bash
   pip install -r requirements.txt
   pip install mysqlclient
   ```

---

## 📞 HELP
- PythonAnywhere Help: https://help.pythonanywhere.com
- Django Documentation: https://docs.djangoproject.com
- Error logs available at: https://www.pythonanywhere.com/web/dpstibariyan_pythonanywhere_com_error_log

---

## ✅ DEPLOYMENT COMPLETE CHECKLIST
- [ ] GitHub repository created
- [ ] Code pushed to GitHub
- [ ] MySQL database created (password saved)
- [ ] Code cloned in PythonAnywhere
- [ ] Virtual environment created
- [ ] Dependencies installed (pip)
- [ ] Database configuration updated (MySQL password added)
- [ ] Database migrations run
- [ ] Admin user created
- [ ] Static files collected
- [ ] WSGI file configured
- [ ] Static files mapped
- [ ] Web app reloaded
- [ ] Application tested and working

---

**Your live application:** https://dpstibariyan.pythonanywhere.com
**Admin panel:** https://dpstibariyan.pythonanywhere.com/admin

Good luck! You're almost there! 🎉
