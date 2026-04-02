# Smart Hospital Appointment Booking System

Minimal full-stack (Flask + SQLite) app that demonstrates:
- Patient registration and appointment booking
- Symptom-based department recommendation (rule-based)
- Doctor daily slot limits and automatic blocking when full
- Simple admin view for departments and doctors

Setup (Windows):


1. Create and activate a Python environment (recommended):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Set your MongoDB connection string in the `MONGODB_URI` environment variable. Example (PowerShell):

```powershell
$env:MONGODB_URI = 'mongodb+srv://jayanth:<db_password>@cluster0.qmmn2m9.mongodb.net/hospital?retryWrites=true&w=majority'
```

Replace `<db_password>` with your Atlas user password. If `MONGODB_URI` is not set, the app will try to use a placeholder connection string — do not use that in production.

Alternatively, create a `.env` file in the project root and add the connection string there:

```
MONGODB_URI="mongodb+srv://jayanth:<db_password>@cluster0.qmmn2m9.mongodb.net/hospital?retryWrites=true&w=majority"
```

The app will automatically load `.env` at startup.

SQLite fallback (local, fast for testing)

To run the app with a local SQLite DB (no Atlas needed):

```powershell
$env:DB_BACKEND = 'sqlite'
python app.py
```

This will create `hospital.db` in the project folder and seed example data.

4. Run the app:

```powershell
python app.py
```

5. Open http://127.0.0.1:5000 in your browser. Use `/book` to book appointments and `/admin` to view seeded data.

Notes:
- DB file `hospital.db` will be created in the project folder.
- To change seed data, edit `db_init.py`.
