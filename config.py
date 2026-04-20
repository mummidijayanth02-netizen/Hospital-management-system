import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24))
    
    # Backend selection: 'mongo' or 'sqlite'. Default is 'mongo'.
    DB_BACKEND = os.environ.get('DB_BACKEND', 'mongo').lower()
    
    # SQLite / SQLAlchemy
    if os.environ.get('VERCEL') == '1' or os.environ.get('RENDER') == 'true':
        default_sqlite = 'sqlite:////tmp/hospital.db'
    else:
        default_sqlite = 'sqlite:///hospital.db'
        
    SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI', default_sqlite)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # MongoDB
    MONGODB_URI = os.environ.get('MONGODB_URI')
    
    # Telehealth / Meeting
    ENABLE_TELEHEALTH = True
