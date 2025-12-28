#!/bin/bash
# PythonAnywhere Deployment Script for School Ledger
# Run this in PythonAnywhere Bash console after cloning the repository

echo "=================================="
echo "School Ledger - PythonAnywhere Setup"
echo "=================================="

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Verify we're in the right directory
echo -e "${BLUE}Step 1: Verifying project directory...${NC}"
if [ ! -f "manage.py" ]; then
    echo "Error: manage.py not found. Make sure you're in the SchoolLedger directory"
    exit 1
fi
echo -e "${GREEN}✓ Project directory verified${NC}"

# Step 2: Create virtual environment (if not already done)
echo -e "${BLUE}Step 2: Creating virtual environment...${NC}"
if mkvirtualenv --python=/usr/bin/python3.10 SchoolLedger; then
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo "Virtual environment might already exist, activating..."
    workon SchoolLedger
fi

# Step 3: Install dependencies
echo -e "${BLUE}Step 3: Installing dependencies...${NC}"
pip install -r requirements.txt
pip install mysqlclient
pip install gunicorn
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Step 4: Display next steps
echo ""
echo -e "${BLUE}=================================="
echo "NEXT STEPS - Do these manually:"
echo "=================================${NC}"
echo ""
echo "1. Go to 'Databases' tab in PythonAnywhere"
echo "   - Create MySQL database"
echo "   - Copy password shown"
echo ""
echo "2. Edit schoolapp/settings.py:"
echo "   nano schoolapp/settings.py"
echo "   Replace DATABASES with MySQL config"
echo "   Add production settings"
echo ""
echo "3. Run migrations:"
echo "   workon SchoolLedger"
echo "   python manage.py migrate"
echo "   python manage.py init_roles"
echo "   python manage.py createsuperuser"
echo "   python manage.py collectstatic --noinput"
echo ""
echo "4. Configure Web App:"
echo "   - Go to 'Web' tab"
echo "   - Add new web app → Django"
echo "   - Update WSGI file with provided config"
echo "   - Add static/media paths"
echo ""
echo "5. Reload web app"
echo ""
echo -e "${GREEN}Script completed! Follow the manual steps above.${NC}"
