# 🚀 School Ledger - PythonAnywhere Deployment Guide

## Account Information
- **Username:** dpstibariyan
- **Password:** Dps@2025
- **Live URL:** https://dpstibariyan.pythonanywhere.com
- **Admin URL:** https://dpstibariyan.pythonanywhere.com/admin
- **Account Type:** Free Tier (can upgrade to $5/month Hacker plan)

---

## Quick Start (5-Step Process)

### **Step 1: GitHub Setup (Local Machine)**
Push your code to GitHub so PythonAnywhere can access it:

```bash
cd c:\LocalFolder\SchoolLedger

# Initialize git (if not done)
git init
git add .
git commit -m "Initial commit - School Ledger RBAC"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR-USERNAME/SchoolLedger.git
git branch -M main
git push -u origin main
```

### **Step 2: PythonAnywhere Database Setup**
1. Login to https://www.pythonanywhere.com (dpstibariyan / Dps@2025)
2. Click **"Databases"** tab
3. Click **"Create a new database"** → MySQL
4. **SAVE THE PASSWORD SHOWN** (you'll need it)
5. Note these details:
   ```
   Database: dpstibariyan$schoolledger
   User: dpstibariyan
   Host: dpstibariyan.mysql.pythonanywhere-services.com
   ```

### **Step 3: Clone & Install (PythonAnywhere Bash)**
1. Go to **"Consoles"** → **"Bash"**
2. Run:
```bash
cd ~
git clone https://github.com/YOUR-USERNAME/SchoolLedger.git
cd SchoolLedger
mkvirtualenv --python=/usr/bin/python3.10 SchoolLedger
pip install -r requirements.txt
pip install mysqlclient gunicorn
```

### **Step 4: Configure Database & Migrations**
1. Still in Bash, create the server-only production file:
```bash
cp production_settings_local.example.py production_settings_local.py
nano production_settings_local.py
```

2. Put your real database settings in it:
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'dpstibariyan$schoolledger',
        'USER': 'dpstibariyan',
        'PASSWORD': 'PASSWORD_FROM_STEP_2',  # Paste the password here
        'HOST': 'dpstibariyan.mysql.pythonanywhere-services.com',
    }
}
```

3. Save: `Ctrl+O` → Enter → `Ctrl+X`

4. Run migrations:
```bash
workon SchoolLedger
python manage.py migrate --settings=production_settings
python manage.py init_roles --settings=production_settings
python manage.py createsuperuser --settings=production_settings
# Create admin account with secure password
python manage.py collectstatic --noinput --settings=production_settings
```

### **Step 5: Configure Web App**
1. Go to **"Web"** tab in PythonAnywhere
2. Click **"Add a new web app"**
3. Choose: Domain: dpstibariyan.pythonanywhere.com → Django → 3.10
4. Click the WSGI file link and replace with:
```python
import os
import sys
path = '/home/dpstibariyan/SchoolLedger'
if path not in sys.path:
    sys.path.append(path)
os.environ['DJANGO_SETTINGS_MODULE'] = 'production_settings'
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```
5. In **"Static files"** section, add:
   - URL: `/static/` → Directory: `/home/dpstibariyan/SchoolLedger/static`
   - URL: `/media/` → Directory: `/home/dpstibariyan/SchoolLedger/media`
6. Click green **"Reload"** button
7. Wait 30 seconds...

---

## ✅ Test Your Deployment

| URL | Purpose |
|-----|---------|
| https://dpstibariyan.pythonanywhere.com | Home page |
| https://dpstibariyan.pythonanywhere.com/accounts/login | Login |
| https://dpstibariyan.pythonanywhere.com/admin | Django admin |
| https://dpstibariyan.pythonanywhere.com/accounts/users | User management |

**Login credentials:**
- Username: `admin`
- Password: [whatever you set in Step 4]

---

## 📁 Files Created for Deployment

1. **requirements.txt** - Python dependencies
2. **production_settings.py** - Stable production wrapper used by the web app
3. **production_settings_local.example.py** - Copy this to production_settings_local.py on the server
4. **DEPLOYMENT_STEPS.md** - Detailed step-by-step guide
5. **deploy.sh** - Bash script to automate setup
6. **This file** - Quick start guide

---

## 🐛 Troubleshooting

### Error: "ModuleNotFoundError"
```bash
workon SchoolLedger
pip install -r requirements.txt
```

### Error: "Database connection refused"
1. Check password in settings.py
2. Verify database exists in Databases tab
3. Ensure host is correct

### Error: "Static files not loading"
```bash
python manage.py collectstatic --clear --noinput
```

### Check Error Logs
```bash
tail -50 /var/log/dpstibariyan.pythonanywhere_com_error_log
```

---

## 📞 Support

- **PythonAnywhere Help:** https://help.pythonanywhere.com/
- **PythonAnywhere Support:** help@pythonanywhere.com
- **Django Docs:** https://docs.djangoproject.com/

---

## 💡 After Deployment

1. **Create staff accounts** - Use admin panel to create teacher/accountant accounts
2. **Assign roles** - Go to `/accounts/users/` to manage roles
3. **Monitor performance** - Check PythonAnywhere dashboard
4. **Upgrade if needed** - Hacker plan ($5/month) for better performance

---

## 📊 Features Available

✅ Employee salary management
✅ Expense tracking
✅ Income tracking
✅ Student fees account
✅ Role-based access control (RBAC)
✅ User management
✅ Multi-user support
✅ Export/Import functionality
✅ Professional login page
✅ Responsive design

---

## 🎓 User Roles Available

1. **Super Admin** - Full access to everything
2. **Admin** - Ledger + user management + statements
3. **Principal** - View-only + user management
4. **Accountant** - Full ledger operations
5. **Teacher** - View employees only
6. **Support Staff** - Basic view access

---

## ⚡ Pricing

- **Free Tier** - Good for testing/small usage
- **Hacker Plan** - $5/month (Recommended for schools)
  - Unlimited web apps
  - Better performance
  - Can support 10,000+ users/day

---

## 🎉 You're All Set!

Your School Ledger application is ready for production. After completing the 5 steps above, your app will be live and accessible worldwide!

**Live URL:** https://dpstibariyan.pythonanywhere.com

Good luck! 🚀
