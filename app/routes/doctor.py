from flask import Blueprint, render_template, session, redirect, url_for, current_app
from app.services.db_service import DBService

doctor_bp = Blueprint('doctor', __name__)

@doctor_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('role') != 'doctor':
        return redirect(url_for('auth.login'))
        
    user_id = session.get('user_id')
    backend = current_app.config['DB_BACKEND']
    
    if backend == 'sqlite':
        from models import Doctor, Appointment
        doctor = Doctor.query.filter_by(user_id=user_id).first()
        appointments = Appointment.query.filter_by(doctor_id=doctor.id).all()
    else:
        from app import mongo
        doctor = mongo.db.doctors.find_one({'user_id': user_id})
        appointments = list(mongo.db.appointments.find({'doctor_id': doctor['_id']}))
        
    return render_template('doctor_dashboard.html', doctor=doctor, appointments=appointments)
