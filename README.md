# Baka Academy Portal

Starter Flask project with admin/teacher login, teacher class-subject assignments, student records, and mark entry restricted to assigned classes and subjects.

## Run on your computer
1. Install Python 3.11+.
2. Open this folder in VS Code.
3. Run:
   ```bash
   python -m venv .venv
   .venv\\Scripts\\activate
   pip install -r requirements.txt
   python app.py
   ```
4. Visit http://127.0.0.1:5000

Initial admin login: `admin` / `ChangeMe123!`. Change it before use.

## Upload to GitHub
Create a new empty repository on GitHub, then open a terminal in this folder:
```bash
git init
git add .
git commit -m "Initial Baka Academy portal"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git
git push -u origin main
```
Replace the URL with your repository URL.

## Important
This is a starter, not a production-ready school system. Before using real student data, add CSRF protection, password change/reset, rate limiting, secure cookies, audit logs, term locking, backups, photo upload validation, HTTPS, and PostgreSQL deployment. Do not upload passwords, secret keys, database files or real student data to GitHub.
