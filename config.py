import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-fallback-secret-key-change-in-production')
    
    # MongoDB
    MONGODB_URI = os.environ.get('MONGODB_URI')
    
    # Backend selection: 'mongo' or 'sqlite'. Default is 'mongo'.
    DB_BACKEND = os.environ.get('DB_BACKEND', 'mongo').lower()
    
    # Auto-fallback to sqlite if mongo URI is missing (to prevent Vercel boot crash)
    if not MONGODB_URI and DB_BACKEND == 'mongo':
        DB_BACKEND = 'sqlite'
    
    # Telehealth / Meeting
    ENABLE_TELEHEALTH = True
