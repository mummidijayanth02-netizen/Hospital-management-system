from flask import Blueprint, render_template, session, current_app
from app.services.db_service import DBService

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    return render_template('index.html')

@main_bp.context_processor
def inject_user():
    # This logic was previously in the global context processor in app.py
    user = None
    patient = None
    doctor = None
    if 'user_id' in session:
        backend = current_app.config['DB_BACKEND']
        if backend == 'sqlite':
            from models import User, Patient, Doctor
            user = User.query.get(session.get('user_id'))
            if session.get('role') == 'patient' and user:
                patient = Patient.query.filter_by(user_id=user.id).first()
            elif session.get('role') == 'doctor' and user:
                doctor = Doctor.query.filter_by(user_id=user.id).first()
        else:
            from app import mongo
            user = mongo.db.users.find_one({'_id': session.get('user_id')})
            if session.get('role') == 'patient':
                patient = mongo.db.patients.find_one({'user_id': session.get('user_id')})
            elif session.get('role') == 'doctor':
                doctor = mongo.db.doctors.find_one({'user_id': session.get('user_id')})
                
    return dict(current_user=user, patient=patient, doctor=doctor)
