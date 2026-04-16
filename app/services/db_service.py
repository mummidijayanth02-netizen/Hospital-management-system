import os
from flask import current_app
from bson.objectid import ObjectId

class DBService:
    @staticmethod
    def get_db_type():
        return current_app.config['DB_BACKEND']

    @staticmethod
    def get_users_collection():
        if DBService.get_db_type() == 'mongo':
            from app import mongo
            return mongo.db.users
        return None  # SQLite uses SQLAlchemy models directly

    @staticmethod
    def get_patient_by_user_id(user_id):
        if DBService.get_db_type() == 'mongo':
            from app import mongo
            return mongo.db.patients.find_one({'user_id': str(user_id)})
        else:
            from models import Patient
            return Patient.query.filter_by(user_id=user_id).first()

    @staticmethod
    def get_doctor_by_user_id(user_id):
        if DBService.get_db_type() == 'mongo':
            from app import mongo
            return mongo.db.doctors.find_one({'user_id': str(user_id)})
        else:
            from models import Doctor
            return Doctor.query.filter_by(user_id=user_id).first()
            
    # Add more abstraction methods as needed here...
    # This keeps the Blueprints (Controllers) clean of backend-specific logic.
