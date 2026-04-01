# Job Portel

Minimal local setup instructions for this Django project (Windows / PowerShell).

## Quick start (PowerShell)

Follow these commands from the project root (where `manage.py` lives).

1) Clone or update the repo

```powershell
# Clone (only if you don't have the repo locally)
git clone <REPOSITORY_URL>
cd job_portel

# Or, if you already have the repo locally, pull the latest changes
git pull origin main
```

2) Create and activate a virtual environment

```powershell
# Create a venv named .venv
python -m venv .venv

# Activate the venv (PowerShell)
.\.venv\Scripts\Activate.ps1
```

3) Install dependencies

```powershell
pip install -r requirements.txt
```

4) Database migrations and run

```powershell

# apply make migration
python manage.py makemigrations

# Apply migrations
python manage.py migrate


# Start dev server
python manage.py runserver
```

5) Open the site

Open http://127.0.0.1:8000/ in your browser.
