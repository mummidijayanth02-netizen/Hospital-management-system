from flask import Blueprint, request, jsonify, session, current_app
from app.services.db_service import DBService
from datetime import datetime

api_bp = Blueprint('api', __name__)

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

# ... other API routes would go here (recommend, book, etc.) ...



from models import Department, Symptom, Doctor, Appointment, Patient, department_symptoms
from app import mongo
from config import Config
DB_BACKEND = Config.DB_BACKEND
from datetime import datetime
import json


@api_bp.route('/recommend', methods=['POST'])
def recommend():
    data = request.json or {}
    symptom_ids = data.get('symptoms', [])
    date_str = data.get('date')
    if DB_BACKEND == 'sqlite':
        # Score departments by symptom mapping via association table
        dept_scores = {}
        for sid in symptom_ids:
            deps = Department.query.join(department_symptoms).filter(department_symptoms.c.symptom_id == sid).all()
            for d in deps:
                dept_scores[d.id] = dept_scores.get(d.id, 0) + 1

        dept_list = []
        if dept_scores:
            for dept_id, score in sorted(dept_scores.items(), key=lambda x: -x[1]):
                d = Department.query.get(dept_id)
                if d:
                    dept_list.append({'id': d.id, 'name': d.name, 'score': score})
        else:
            for d in Department.query.all():
                dept_list.append({'id': d.id, 'name': d.name, 'score': 0})

        recommended = []
        if dept_list:
            top_dept_id = dept_list[0]['id']
            docs = Doctor.query.filter_by(department_id=top_dept_id).all()
            for doc in docs:
                available = True
                if date_str:
                    try:
                        appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        count = Appointment.query.filter_by(doctor_id=doc.id, date=str(appt_date)).count()
                        if count >= doc.daily_slot_limit:
                            available = False
                    except Exception:
                        pass
                recommended.append({'id': doc.id, 'name': doc.name, 'available': available, 'daily_slot_limit': doc.daily_slot_limit})

        return jsonify({'departments': dept_list, 'doctors': recommended})
    else:
        # Mongo path (existing)
        dept_scores = {}
        for sid in symptom_ids:
            matches = mongo.db.departments.find({'symptom_ids': sid})
            for dept in matches:
                did = dept.get('id')
                dept_scores[did] = dept_scores.get(did, 0) + 1

        dept_list = []
        if dept_scores:
            for dept_id, score in sorted(dept_scores.items(), key=lambda x: -x[1]):
                dept = mongo.db.departments.find_one({'id': dept_id})
                if dept:
                    dept_list.append({'id': dept['id'], 'name': dept['name'], 'score': score})
        else:
            for d in mongo.db.departments.find():
                dept_list.append({'id': d['id'], 'name': d['name'], 'score': 0})

        recommended = []
        if dept_list:
            top_dept_id = dept_list[0]['id']
            for doc in mongo.db.doctors.find({'department_id': top_dept_id}):
                available = True
                if date_str:
                    try:
                        appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                        count = mongo.db.appointments.count_documents({'doctor_id': doc['id'], 'date': str(appt_date)})
                        if count >= doc.get('daily_slot_limit', 0):
                            available = False
                    except Exception:
                        pass
                recommended.append({'id': doc['id'], 'name': doc['name'], 'available': available, 'daily_slot_limit': doc.get('daily_slot_limit', 0)})

        return jsonify({'departments': dept_list, 'doctors': recommended})




@api_bp.route('/book', methods=['POST'])
def book():
    data = request.json or {}
    patient_name = data.get('name')
    phone = data.get('phone')
    email = data.get('email')
    doctor_id = data.get('doctor_id')
    date_str = data.get('date')

    if not (patient_name and doctor_id and date_str):
        return jsonify({'success': False, 'message': 'Missing required fields'}), 400

    if DB_BACKEND == 'sqlite':
        # find or create patient
        patient = Patient.query.filter_by(phone=phone).first()
        if not patient:
            patient = Patient(name=patient_name, phone=phone, email=email)
            db.session.add(patient)
            db.session.commit()

        # check doctor
        doctor = Doctor.query.get(int(doctor_id))
        if not doctor:
            return jsonify({'success': False, 'message': 'Doctor not found'}), 404

        try:
            appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except Exception:
            return jsonify({'success': False, 'message': 'Invalid date format; use YYYY-MM-DD'}), 400

        count = Appointment.query.filter_by(doctor_id=doctor.id, date=str(appt_date)).count()
        if count >= doctor.daily_slot_limit:
            return jsonify({'success': False, 'message': 'No slots available for selected doctor on this date'}), 409

        appt = Appointment(patient_id=patient.id, doctor_id=doctor.id, date=str(appt_date), time=data.get('time', ''), status='scheduled')
        db.session.add(appt)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Appointment booked', 'appointment_id': appt.id})
    else:
        # mongo path
        patient = mongo.db.patients.find_one({'phone': phone})
        if not patient:
            res = mongo.db.patients.insert_one({'name': patient_name, 'phone': phone, 'email': email})
            patient_id = str(res.inserted_id)
        else:
            patient_id = str(patient['_id'])

        doctor = mongo.db.doctors.find_one({'id': int(doctor_id)})
        if not doctor:
            return jsonify({'success': False, 'message': 'Doctor not found'}), 404

        try:
            appt_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except Exception:
            return jsonify({'success': False, 'message': 'Invalid date format; use YYYY-MM-DD'}), 400

        count = mongo.db.appointments.count_documents({'doctor_id': doctor['id'], 'date': str(appt_date)})
        if count >= doctor.get('daily_slot_limit', 0):
            return jsonify({'success': False, 'message': 'No slots available for selected doctor on this date'}), 409

        appt = {
            'patient_id': patient_id,
            'doctor_id': doctor['id'],
            'date': str(appt_date),
            'time': data.get('time', ''),
            'status': 'scheduled',
            'created_at': datetime.utcnow()
        }

        res = mongo.db.appointments.insert_one(appt)
        return jsonify({'success': True, 'message': 'Appointment booked', 'appointment_id': str(res.inserted_id)})


# Admin CRUD APIs




@api_bp.route('/admin/departments', methods=['GET', 'POST'])
def admin_departments():
    if DB_BACKEND == 'sqlite':
        if request.method == 'GET':
            depts = Department.query.all()
            return jsonify([{'id': d.id, 'name': d.name, 'symptom_ids': [s.id for s in d.symptoms]} for d in depts])
        data = request.json or {}
        name = data.get('name')
        symptom_ids = data.get('symptom_ids', [])
        if not name:
            return jsonify({'success': False, 'message': 'Name required'}), 400
        dept = Department(name=name)
        db.session.add(dept)
        db.session.commit()
        # attach symptoms
        for sid in symptom_ids:
            s = Symptom.query.get(sid)
            if s:
                dept.symptoms.append(s)
        db.session.commit()
        return jsonify({'success': True, 'department': {'id': dept.id, 'name': dept.name}})
    else:
        if request.method == 'GET':
            depts = list(mongo.db.departments.find())
            return jsonify(depts)
        data = request.json or {}
        name = data.get('name')
        symptom_ids = data.get('symptom_ids', [])
        if not name:
            return jsonify({'success': False, 'message': 'Name required'}), 400
        # assign numeric id
        cur = mongo.db.departments.find_one(sort=[('id', -1)])
        nid = (cur['id'] if cur else 0) + 1
        doc = {'id': nid, 'name': name, 'symptom_ids': symptom_ids}
        mongo.db.departments.insert_one(doc)
        return jsonify({'success': True, 'department': doc})




@api_bp.route('/admin/departments/<int:dept_id>', methods=['PUT', 'DELETE'])
def admin_department_modify(dept_id):
    if DB_BACKEND == 'sqlite':
        if request.method == 'DELETE':
            Department.query.filter_by(id=dept_id).delete()
            db.session.commit()
            return jsonify({'success': True})
        data = request.json or {}
        dept = Department.query.get(dept_id)
        if not dept:
            return jsonify({'success': False}), 404
        dept.name = data.get('name')
        dept.symptoms = []
        for sid in data.get('symptom_ids', []):
            s = Symptom.query.get(sid)
            if s:
                dept.symptoms.append(s)
        db.session.commit()
        return jsonify({'success': True})
    else:
        if request.method == 'DELETE':
            mongo.db.departments.delete_one({'id': dept_id})
            return jsonify({'success': True})
        data = request.json or {}
        mongo.db.departments.update_one({'id': dept_id}, {'$set': {'name': data.get('name'), 'symptom_ids': data.get('symptom_ids', [])}})
        return jsonify({'success': True})




@api_bp.route('/admin/symptoms', methods=['GET', 'POST'])
def admin_symptoms():
    if DB_BACKEND == 'sqlite':
        if request.method == 'GET':
            return jsonify([{'id': s.id, 'name': s.name} for s in Symptom.query.all()])
        data = request.json or {}
        name = data.get('name')
        if not name:
            return jsonify({'success': False, 'message': 'Name required'}), 400
        s = Symptom(name=name)
        db.session.add(s)
        db.session.commit()
        return jsonify({'success': True, 'symptom': {'id': s.id, 'name': s.name}})
    else:
        if request.method == 'GET':
            return jsonify(list(mongo.db.symptoms.find()))
        data = request.json or {}
        name = data.get('name')
        if not name:
            return jsonify({'success': False, 'message': 'Name required'}), 400
        cur = mongo.db.symptoms.find_one(sort=[('id', -1)])
        nid = (cur['id'] if cur else 0) + 1
        doc = {'id': nid, 'name': name}
        mongo.db.symptoms.insert_one(doc)
        return jsonify({'success': True, 'symptom': doc})




@api_bp.route('/admin/symptoms/<int:sym_id>', methods=['PUT', 'DELETE'])
def admin_symptom_modify(sym_id):
    if DB_BACKEND == 'sqlite':
        if request.method == 'DELETE':
            Symptom.query.filter_by(id=sym_id).delete()
            db.session.commit()
            # remove associations
            return jsonify({'success': True})
        data = request.json or {}
        s = Symptom.query.get(sym_id)
        if not s:
            return jsonify({'success': False}), 404
        s.name = data.get('name')
        db.session.commit()
        return jsonify({'success': True})
    else:
        if request.method == 'DELETE':
            mongo.db.symptoms.delete_one({'id': sym_id})
            # Also remove from departments
            mongo.db.departments.update_many({}, {'$pull': {'symptom_ids': sym_id}})
            return jsonify({'success': True})
        data = request.json or {}
        mongo.db.symptoms.update_one({'id': sym_id}, {'$set': {'name': data.get('name')}})
        return jsonify({'success': True})




@api_bp.route('/admin/doctors', methods=['GET', 'POST'])
def admin_doctors():
    if DB_BACKEND == 'sqlite':
        if request.method == 'GET':
            return jsonify([{'id': d.id, 'name': d.name, 'department_id': d.department_id, 'daily_slot_limit': d.daily_slot_limit} for d in Doctor.query.all()])
        data = request.json or {}
        name = data.get('name')
        department_id = data.get('department_id')
        daily_slot_limit = int(data.get('daily_slot_limit', 0))
        if not (name and department_id):
            return jsonify({'success': False, 'message': 'Name and department required'}), 400
        doc = Doctor(name=name, department_id=int(department_id), daily_slot_limit=daily_slot_limit)
        db.session.add(doc)
        db.session.commit()
        return jsonify({'success': True, 'doctor': {'id': doc.id, 'name': doc.name}})
    else:
        if request.method == 'GET':
            return jsonify(list(mongo.db.doctors.find()))
        data = request.json or {}
        name = data.get('name')
        department_id = data.get('department_id')
        daily_slot_limit = int(data.get('daily_slot_limit', 0))
        if not (name and department_id):
            return jsonify({'success': False, 'message': 'Name and department required'}), 400
        cur = mongo.db.doctors.find_one(sort=[('id', -1)])
        nid = (cur['id'] if cur else 0) + 1
        doc = {'id': nid, 'name': name, 'department_id': int(department_id), 'daily_slot_limit': daily_slot_limit}
        mongo.db.doctors.insert_one(doc)
        return jsonify({'success': True, 'doctor': doc})




@api_bp.route('/admin/doctors/<int:doc_id>', methods=['PUT', 'DELETE'])
def admin_doctor_modify(doc_id):
    if DB_BACKEND == 'sqlite':
        if request.method == 'DELETE':
            Doctor.query.filter_by(id=doc_id).delete()
            db.session.commit()
            return jsonify({'success': True})
        data = request.json or {}
        doc = Doctor.query.get(doc_id)
        if not doc:
            return jsonify({'success': False}), 404
        doc.name = data.get('name')
        doc.department_id = int(data.get('department_id'))
        doc.daily_slot_limit = int(data.get('daily_slot_limit', 0))
        db.session.commit()
        return jsonify({'success': True})
    else:
        if request.method == 'DELETE':
            mongo.db.doctors.delete_one({'id': doc_id})
            return jsonify({'success': True})
        data = request.json or {}
        mongo.db.doctors.update_one({'id': doc_id}, {'$set': {'name': data.get('name'), 'department_id': int(data.get('department_id')), 'daily_slot_limit': int(data.get('daily_slot_limit', 0))}})
        return jsonify({'success': True})


# Appointments listing and export


@api_bp.route('/appointments', methods=['GET'])
def list_appointments():
    q = {}
    doctor_id = request.args.get('doctor_id')
    date = request.args.get('date')
    if doctor_id:
        q['doctor_id'] = int(doctor_id)
    if date:
        q['date'] = date
    if DB_BACKEND == 'sqlite':
        qsql = Appointment.query
        if doctor_id:
            qsql = qsql.filter_by(doctor_id=int(doctor_id))
        if date:
            qsql = qsql.filter_by(date=date)
        appts = qsql.order_by(Appointment.id.desc()).all()
        out = []
        for a in appts:
            pat = Patient.query.get(a.patient_id)
            doc = Doctor.query.get(a.doctor_id)
            out.append({'id': a.id, 'patient': pat.name if pat else a.patient_id, 'doctor': doc.name if doc else a.doctor_id, 'date': a.date, 'time': a.time, 'status': a.status})
        return jsonify(out)
    else:
        appts = list(mongo.db.appointments.find(q).sort('created_at', -1))
        out = []
        for a in appts:
            pat = mongo.db.patients.find_one({'_id': ObjectId(a['patient_id'])})
            doc = mongo.db.doctors.find_one({'id': a['doctor_id']})
            out.append({'id': str(a.get('_id')), 'patient': pat.get('name') if pat else a.get('patient_id'), 'doctor': doc.get('name') if doc else a.get('doctor_id'), 'date': a.get('date'), 'time': a.get('time'), 'status': a.get('status')})
        return jsonify(out)




@api_bp.route('/appointments/export', methods=['GET'])
def export_appointments():
    import csv
    from io import StringIO
    q = {}
    doctor_id = request.args.get('doctor_id')
    date = request.args.get('date')
    if doctor_id:
        q['doctor_id'] = int(doctor_id)
    if date:
        q['date'] = date
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['AppointmentID', 'Patient', 'Doctor', 'Date', 'Time', 'Status'])
    if DB_BACKEND == 'sqlite':
        qsql = Appointment.query
        if doctor_id:
            qsql = qsql.filter_by(doctor_id=int(doctor_id))
        if date:
            qsql = qsql.filter_by(date=date)
        appts = qsql.order_by(Appointment.id.desc()).all()
        for a in appts:
            pat = Patient.query.get(a.patient_id)
            doc = Doctor.query.get(a.doctor_id)
            writer.writerow([a.id, pat.name if pat else a.patient_id, doc.name if doc else a.doctor_id, a.date, a.time, a.status])
    else:
        appts = list(mongo.db.appointments.find(q).sort('created_at', -1))
        for a in appts:
            pat = mongo.db.patients.find_one({'_id': ObjectId(a['patient_id'])})
            doc = mongo.db.doctors.find_one({'id': a['doctor_id']})
            writer.writerow([str(a.get('_id')), pat.get('name') if pat else a.get('patient_id'), doc.get('name') if doc else a.get('doctor_id'), a.get('date'), a.get('time'), a.get('status')])
    csv_data = si.getvalue()
    from flask import Response
    return Response(csv_data, mimetype='text/csv', headers={'Content-Disposition':'attachment; filename=appointments.csv'})


