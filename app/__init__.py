from flask import Flask
from config import Config
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_pymongo import PyMongo
import certifi
import os

# Globals for extensions
db = SQLAlchemy()
mongo = PyMongo()

def create_app(config_class=Config):
    app = Flask(__name__, 
                template_folder='../templates', 
                static_folder='../static')
    app.config.from_object(config_class)

    # Initialize CORS
    CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

    # Initialize DB Backend
    if app.config['DB_BACKEND'] == 'sqlite':
        db.init_app(app)
        # Import models to ensure they are registered
        with app.app_context():
            from models import User
            db.create_all()
    else:
        app.config['MONGO_URI'] = app.config['MONGODB_URI']
        mongo.init_app(app, tlsCAFile=certifi.where())
        # Seed data if needed
        with app.app_context():
            try:
                from db_init import init_db
                init_db(mongo)
            except Exception as e:
                print(f"DB seed skipped or failed: {e}")

    # Register Blueprints
    from app.routes.auth import auth_bp
    from app.routes.patient import patient_bp
    from app.routes.doctor import doctor_bp
    from app.routes.api import api_bp
    from app.routes.main import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(patient_bp, url_prefix='/patient')
    app.register_blueprint(doctor_bp, url_prefix='/doctor')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(main_bp)

    return app
