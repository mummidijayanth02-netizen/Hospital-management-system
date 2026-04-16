from flask import Blueprint, render_template, session, redirect, url_for, current_app
from app.services.db_service import DBService

patient_bp = Blueprint('patient', __name__)

@patient_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('role') != 'patient':
        return redirect(url_for('auth.login'))
        
    user_id = session.get('user_id')
    backend = current_app.config['DB_BACKEND']
    
    if backend == 'sqlite':
        from models import Patient, Appointment, Notification
        patient = Patient.query.filter_by(user_id=user_id).first()
        appointments = Appointment.query.filter_by(patient_id=patient.id).all()
        notifications = Notification.query.filter_by(user_id=user_id).order_by(Notification.created_at.desc()).all()
    else:
        from app import mongo
        patient = mongo.db.patients.find_one({'user_id': user_id})
        appointments = list(mongo.db.appointments.find({'patient_id': patient['_id']}))
        notifications = list(mongo.db.notifications.find({'user_id': user_id}).sort('created_at', -1))
        
    return render_template('patient_dashboard.html', patient=patient, appointments=appointments, notifications=notifications)
