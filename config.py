import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24))
    
    # Backend selection: 'mongo' or 'sqlite'. Default is 'mongo'.
    DB_BACKEND = os.environ.get('DB_BACKEND', os.environ.get('DATABASE', 'mongo')).lower()
    
    # SQLite / SQLAlchemy
    SQLALCHEMY_DATABASE_URI = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///hospital.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # MongoDB
    MONGODB_URI = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/hospital_fallback')
    
    # Telehealth / Meeting
    ENABLE_TELEHEALTH = True
