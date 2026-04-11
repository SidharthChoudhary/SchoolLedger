# 📋 PythonAnywhere Deployment Checklist

## Account Details
```
Username: dpstibariyan
Password: Dps@2025
Domain: dpstibariyan.pythonanywhere.com
```

---

## ☐ PHASE 1: LOCAL PREPARATION

- [ ] Navigate to project: `cd c:\LocalFolder\SchoolLedger`
- [ ] Initialize git: `git init`
- [ ] Add all files: `git add .`
- [ ] Create GitHub repository
- [ ] Set git remote: `git remote add origin https://github.com/YOUR-USERNAME/SchoolLedger.git`
- [ ] Push to GitHub: `git push -u origin main`
- [ ] Verify requirements.txt exists
- [ ] Verify production_settings.py exists
- [ ] Verify production_settings_local.example.py exists

---

## ☐ PHASE 2: PYTHONANYWHERE ACCOUNT

- [ ] Login to https://www.pythonanywhere.com
  - Username: dpstibariyan
  - Password: Dps@2025
- [ ] Go to "Databases" tab
- [ ] Click "Create a new database"
- [ ] Choose MySQL
- [ ] **SAVE DATABASE PASSWORD**
- [ ] Note database connection details:
  - [ ] Database name: dpstibariyan$schoolledger
  - [ ] User: dpstibariyan
  - [ ] Host: dpstibariyan.mysql.pythonanywhere-services.com
  - [ ] Password: [SAVED]

---

## ☐ PHASE 3: CODE DEPLOYMENT

### Clone Repository
- [ ] Go to "Consoles" → "Bash"
- [ ] Run: `cd ~`
- [ ] Run: `git clone https://github.com/YOUR-USERNAME/SchoolLedger.git`
- [ ] Run: `cd SchoolLedger`

### Create Virtual Environment
- [ ] Run: `mkvirtualenv --python=/usr/bin/python3.10 SchoolLedger`
- [ ] Verify: `(SchoolLedger)` appears in prompt

### Install Dependencies
- [ ] Run: `pip install -r requirements.txt`
- [ ] Run: `pip install mysqlclient`
- [ ] Run: `pip install gunicorn`
- [ ] Verify all install without errors

---

## ☐ PHASE 4: CONFIGURATION

### Create local production settings
- [ ] Run: `cp production_settings_local.example.py production_settings_local.py`
- [ ] Run: `nano production_settings_local.py`
- [ ] Paste database password where needed
- [ ] Verify ALLOWED_HOSTS and static/media paths are correct
- [ ] Save file: `Ctrl+O` → `Enter` → `Ctrl+X`
- [ ] Verify: `cat production_settings_local.py | grep PASSWORD`

---

## ☐ PHASE 5: DATABASE SETUP

### Run Migrations
- [ ] Run: `workon SchoolLedger`
- [ ] Run: `python manage.py migrate --settings=production_settings`
  - [ ] Verify: "Operations to perform:" appears
  - [ ] Verify: All tables created
- [ ] Run: `python manage.py init_roles --settings=production_settings`
  - [ ] Verify: 6 roles created with permissions

### Create Admin User
- [ ] Run: `python manage.py createsuperuser --settings=production_settings`
- [ ] Enter username: `admin`
- [ ] Enter email: `admin@school.local`
- [ ] Enter password: [choose secure one]
- [ ] Confirm password
- [ ] Verify: "Superuser created successfully"

### Collect Static Files
- [ ] Run: `python manage.py collectstatic --noinput --settings=production_settings`
- [ ] Verify: "files copied to" message

---

## ☐ PHASE 6: WEB APP CONFIGURATION

### Create Web App
- [ ] Go to "Web" tab in PythonAnywhere
- [ ] Click "Add a new web app"
- [ ] Choose domain: `dpstibariyan.pythonanywhere.com`
- [ ] Choose framework: **Django**
- [ ] Choose Python: **3.10**
- [ ] Click "Next" to create

### Configure WSGI
- [ ] Click the blue WSGI file link
- [ ] Delete all existing code
- [ ] Paste provided WSGI configuration
- [ ] Click "Save"
- [ ] Verify file shows new config

### Configure Static Files
- [ ] Scroll to "Static files" section
- [ ] Click "Add static files mapping"
- [ ] Mapping 1:
  - [ ] URL: `/static/`
  - [ ] Directory: `/home/dpstibariyan/SchoolLedger/static`
- [ ] Click "Add another"
- [ ] Mapping 2:
  - [ ] URL: `/media/`
  - [ ] Directory: `/home/dpstibariyan/SchoolLedger/media`
- [ ] Verify both mappings appear

---

## ☐ PHASE 7: DEPLOYMENT

- [ ] In "Web" tab, click green **"Reload dpstibariyan.pythonanywhere.com"** button
- [ ] Wait 30 seconds for restart
- [ ] Watch for green checkmark indicating "Web app is running"

---

## ☐ PHASE 8: TESTING

### Test URLs
- [ ] **Home Page:** https://dpstibariyan.pythonanywhere.com
  - [ ] Should show school ledger homepage
- [ ] **Login Page:** https://dpstibariyan.pythonanywhere.com/accounts/login
  - [ ] Should show login form
- [ ] **Test Login:** 
  - [ ] Username: admin
  - [ ] Password: [the one you created]
  - [ ] Should redirect to profile page
- [ ] **Admin Panel:** https://dpstibariyan.pythonanywhere.com/admin
  - [ ] Should show Django admin
  - [ ] Should be able to login
- [ ] **User Management:** https://dpstibariyan.pythonanywhere.com/accounts/users
  - [ ] Should show user list

---

## ☐ PHASE 9: VERIFICATION

- [ ] Homepage loads without errors
- [ ] Login works correctly
- [ ] Can access admin panel
- [ ] Can access user management
- [ ] Static files load (CSS styling present)
- [ ] All menu items visible and clickable
- [ ] Database is working (accounts visible)

---

## ☐ PHASE 10: POST-DEPLOYMENT

- [ ] Create staff accounts in admin
- [ ] Assign roles to staff
- [ ] Test role-based access
- [ ] Monitor error logs (if any)
- [ ] Consider upgrading to Hacker plan if needed
- [ ] Configure email notifications (optional)
- [ ] Set up backup strategy

---

## ✅ DEPLOYMENT COMPLETE!

Your application is now live at:
**https://dpstibariyan.pythonanywhere.com**

Admin access at:
**https://dpstibariyan.pythonanywhere.com/admin**

---

## 🔧 Useful Commands (For Future Reference)

```bash
# Activate virtual environment
workon SchoolLedger

# Deactivate virtual environment
deactivate

# Check Python version
python --version

# Install additional packages
pip install package-name

# Run migrations
python manage.py migrate

# Create new superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic

# View error logs
tail -50 /var/log/dpstibariyan.pythonanywhere_com_error_log

# Check disk usage
du -sh /home/dpstibariyan/
```

---

## 📞 Support & Troubleshooting

### If Database Error:
1. Verify password in settings.py matches
2. Check database exists in "Databases" tab
3. Verify MySQL is running

### If Static Files Missing:
```bash
python manage.py collectstatic --clear --noinput
# Then reload web app
```

### If ModuleNotFoundError:
```bash
pip install -r requirements.txt
```

### Check Status:
- Error log: https://www.pythonanywhere.com/web/dpstibariyan_pythonanywhere_com_error_log
- Contact: help@pythonanywhere.com

---

**Date Deployed:** _______________
**Deployed By:** _______________
**Notes:** _______________________________________________

