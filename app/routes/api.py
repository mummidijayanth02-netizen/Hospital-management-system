from flask import Blueprint, request, jsonify, session, current_app
from app.services.db_service import DBService
from datetime import datetime
import uuid

api_bp = Blueprint('api', __name__)


@api_bp.route('/recommend', methods=['POST'])
def recommend():
    """AI-based department + doctor recommendation from symptoms."""
    data = request.get_json()
    symptom_ids = data.get('symptoms', [])
    date = data.get('date', '')
    backend = current_app.config['DB_BACKEND']

    departments_scored = []
    available_doctors = []

    if backend == 'sqlite':
        from models import Department, Doctor, Appointment
        depts = Department.query.all()
        for dept in depts:
            dept_symptom_ids = [s.id for s in dept.symptoms]
            score = len(set(symptom_ids) & set(dept_symptom_ids))
            if score > 0:
                departments_scored.append({'name': dept.name, 'score': score, 'id': dept.id})

        departments_scored.sort(key=lambda d: d['score'], reverse=True)

        for dept in departments_scored:
            docs = Doctor.query.filter_by(department_id=dept['id']).all()
            for doc in docs:
                booked = Appointment.query.filter_by(doctor_id=doc.id, date=date).count() if date else 0
                available_doctors.append({
                    'id': doc.id,
                    'name': doc.name,
                    'available': booked < doc.daily_slot_limit
                })
    else:
        from app import mongo
        depts = list(mongo.db.departments.find())
        for dept in depts:
            dept_symptom_ids = dept.get('symptom_ids', [])
            score = len(set(symptom_ids) & set(dept_symptom_ids))
            if score > 0:
                departments_scored.append({'name': dept['name'], 'score': score, 'id': dept['id']})

        departments_scored.sort(key=lambda d: d['score'], reverse=True)

        for dept in departments_scored:
            docs = list(mongo.db.doctors.find({'department_id': dept['id']}))
            for doc in docs:
                booked = mongo.db.appointments.count_documents({'doctor_id': doc['id'], 'date': date}) if date else 0
                available_doctors.append({
                    'id': doc['id'],
                    'name': doc['name'],
                    'available': booked < doc.get('daily_slot_limit', 10)
                })

    return jsonify({'departments': departments_scored, 'doctors': available_doctors})


@api_bp.route('/book', methods=['POST'])
def book():
    """Book an appointment with a specific doctor."""
    data = request.get_json()
    name = data.get('name')
    phone = data.get('phone')
    email = data.get('email', '')
    doctor_id = data.get('doctor_id')
    date = data.get('date')
    appointment_type = data.get('appointment_type', 'in-person')
    backend = current_app.config['DB_BACKEND']

    if not name or not phone or not doctor_id or not date:
        return jsonify({'success': False, 'message': 'Missing required fields'})

    telehealth_url = None
    telehealth_passcode = None
    if appointment_type == 'telehealth':
        meeting_id = str(uuid.uuid4())[:8]
        telehealth_url = f'/telehealth/{meeting_id}'
        telehealth_passcode = str(uuid.uuid4())[:6].upper()

    if backend == 'sqlite':
        from models import Patient, Appointment, Notification
        from app import db
        patient = Patient.query.filter_by(phone=phone).first()
        if not patient:
            # Create a guest patient record
            patient = Patient(name=name, phone=phone, email=email)
            db.session.add(patient)
            db.session.commit()

        appt = Appointment(
            patient_id=patient.id,
            doctor_id=doctor_id,
            date=date,
            status='scheduled',
            appointment_type=appointment_type,
            telehealth_url=telehealth_url,
            telehealth_passcode=telehealth_passcode
        )
        db.session.add(appt)
        db.session.commit()

        # Notification for logged-in patient
        if patient.user_id:
            notif = Notification(
                user_id=patient.user_id,
                title='Appointment Booked',
                message=f'Your {appointment_type} appointment on {date} has been confirmed.',
                category='appointment'
            )
            db.session.add(notif)
            db.session.commit()

        return jsonify({
            'success': True,
            'appointment_id': appt.id,
            'telehealth_url': telehealth_url,
            'telehealth_passcode': telehealth_passcode
        })
    else:
        from app import mongo
        patient = mongo.db.patients.find_one({'phone': phone})
        if not patient:
            patient_id = str(uuid.uuid4())
            mongo.db.patients.insert_one({
                '_id': patient_id,
                'name': name,
                'phone': phone,
                'email': email
            })
        else:
            patient_id = str(patient['_id'])

        appt_id = str(uuid.uuid4())[:8]
        mongo.db.appointments.insert_one({
            'id': appt_id,
            'patient_id': patient_id,
            'doctor_id': doctor_id,
            'date': date,
            'status': 'scheduled',
            'appointment_type': appointment_type,
            'telehealth_url': telehealth_url,
            'telehealth_passcode': telehealth_passcode
        })

        # Notification for logged-in patient
        if patient and patient.get('user_id'):
            mongo.db.notifications.insert_one({
                'user_id': patient['user_id'],
                'title': 'Appointment Booked',
                'message': f'Your {appointment_type} appointment on {date} has been confirmed.',
                'category': 'appointment',
                'is_read': False,
                'created_at': datetime.utcnow()
            })

        return jsonify({
            'success': True,
            'appointment_id': appt_id,
            'telehealth_url': telehealth_url,
            'telehealth_passcode': telehealth_passcode
        })


@api_bp.route('/notifications', methods=['GET'])
def get_notifications():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required'}), 403

    backend = current_app.config['DB_BACKEND']
    if backend == 'sqlite':
        from models import Notification
        notifs = Notification.query.filter_by(user_id=session['user_id']).order_by(Notification.created_at.desc()).all()
        return jsonify([{
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'category': n.category,
            'is_read': n.is_read,
            'created_at': str(n.created_at)
        } for n in notifs])
    else:
        from app import mongo
        notifs = list(mongo.db.notifications.find({'user_id': str(session['user_id'])}).sort('created_at', -1))
        return jsonify([{
            'id': str(n['_id']),
            'title': n.get('title'),
            'message': n.get('message'),
            'category': n.get('category'),
            'is_read': n.get('is_read', False),
            'created_at': str(n.get('created_at'))
        } for n in notifs])


@api_bp.route('/notifications/unread-count', methods=['GET'])
def unread_notification_count():
    if 'user_id' not in session:
        return jsonify({'count': 0})

    backend = current_app.config['DB_BACKEND']
    if backend == 'sqlite':
        from models import Notification
        count = Notification.query.filter_by(user_id=session['user_id'], is_read=False).count()
    else:
        from app import mongo
        count = mongo.db.notifications.count_documents({'user_id': str(session['user_id']), 'is_read': False})
    return jsonify({'count': count})


@api_bp.route('/appointments', methods=['GET'])
def get_appointments():
    backend = current_app.config['DB_BACKEND']
    doctor_id = request.args.get('doctor_id')
    date = request.args.get('date')

    if backend == 'sqlite':
        from models import Appointment, Patient, Doctor
        query = Appointment.query
        if doctor_id:
            query = query.filter_by(doctor_id=int(doctor_id))
        if date:
            query = query.filter_by(date=date)
        appts = query.all()
        return jsonify([{
            'patient': a.patient.name if a.patient else 'N/A',
            'doctor': a.doctor.name if a.doctor else 'N/A',
            'date': a.date,
            'time': a.time or '',
            'status': a.status
        } for a in appts])
    else:
        from app import mongo
        filt = {}
        if doctor_id:
            filt['doctor_id'] = int(doctor_id)
        if date:
            filt['date'] = date
        appts = list(mongo.db.appointments.find(filt))

        result = []
        for a in appts:
            patient = mongo.db.patients.find_one({'_id': a.get('patient_id')})
            doctor = mongo.db.doctors.find_one({'id': a.get('doctor_id')})
            result.append({
                'patient': patient['name'] if patient else 'N/A',
                'doctor': doctor['name'] if doctor else 'N/A',
                'date': a.get('date', ''),
                'time': a.get('time', ''),
                'status': a.get('status', '')
            })
        return jsonify(result)
