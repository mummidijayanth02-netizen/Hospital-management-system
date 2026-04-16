from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
import os
import hashlib
import uuid
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash

# Load environment variables from .env if present
load_dotenv()

# Backend selection: 'mongo' or 'sqlite'. Default is 'mongo'.
DB_BACKEND = os.environ.get('DB_BACKEND', os.environ.get('DATABASE', 'mongo')).lower()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))

from flask_cors import CORS
# Enable CORS for all routes and origins
CORS(app, resources={r"/*": {"origins": "*"}}, supports_credentials=True)

# Global Error Handlers
@app.errorhandler(404)
def not_found_error(error):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': 'Resource not found', 'error': '404', 'details': str(error)}), 404
    return render_template('index.html'), 404 # Redirect to index or a 404 page

@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({'success': False, 'message': 'Internal Server Error', 'error': '500', 'details': str(error)}), 500

@app.errorhandler(503)
def service_unavailable_error(error):
    return jsonify({'success': False, 'message': 'Service Unavailable', 'error': '503', 'details': str(error)}), 503

@app.errorhandler(505)
def http_version_not_supported(error):
    return jsonify({'success': False, 'message': 'HTTP Version Not Supported', 'error': '505', 'details': str(error)}), 505

@app.errorhandler(Exception)
def handle_exception(e):
    # Log the general exception
    app.logger.error(f'Unhandled Exception: {e}')
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': 'An unexpected error occurred.', 'details': str(e)}), 500
    # For regular pages, return a generic error message
    return f"<h3>An unexpected error occurred.</h3><p>Details: {str(e)}</p>", 500

if DB_BACKEND == 'sqlite':
    # SQLAlchemy setup (local SQLite)
    from models import db, Patient, Department, Symptom, Doctor, Appointment, department_symptoms, User, Prescription, Notification
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///hospital.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    from sqlite_init import init_db as init_sqlite_db
    mongo = None

    # perform initialization immediately so it runs under flask run as well
    with app.app_context():
        try:
            init_sqlite_db()
        except Exception as e:
            print('Warning: SQLite DB initialization failed during import:', e)
else:
    # MongoDB setup
    from flask_pymongo import PyMongo
    from bson.objectid import ObjectId
    import certifi
    
    app.config['MONGO_URI'] = os.environ.get('MONGODB_URI', 'mongodb://localhost:27017/hospital_fallback')
    mongo = PyMongo(app, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=5000)

    # initialize mongo too
    with app.app_context():
        try:
            from db_init import init_db
            if mongo.db is not None:
                init_db(mongo)
            else:
                print('Warning: MongoDB initialization failed - mongo.db is None. Check your MONGO_URI.')
        except Exception as e:
            print('Warning: MongoDB initialization failed during import:', e)


# Seed initialization will be run when starting the app directly.

# Context processor for current user
@app.context_processor
def inject_user():
    user = None
    patient = None
    doctor = None
    if 'user_id' in session:
        if DB_BACKEND == 'sqlite':
            user = User.query.get(session.get('user_id'))
            if session.get('role') == 'patient' and user:
                patient = Patient.query.filter_by(user_id=user.id).first()
            elif session.get('role') == 'doctor' and user:
                doctor = Doctor.query.filter_by(user_id=user.id).first()
        else:
            try:
                from bson.objectid import ObjectId
                user = mongo.db.users.find_one({'_id': ObjectId(session.get('user_id'))})
                if session.get('role') == 'patient' and user:
                    patient = mongo.db.patients.find_one({'user_id': str(user['_id'])})
                elif session.get('role') == 'doctor' and user:
                    doctor = mongo.db.doctors.find_one({'user_id': str(user['_id'])})
                    if doctor:
                        doctor['department'] = mongo.db.departments.find_one({'id': doctor.get('department_id')})
            except Exception:
                pass
    return {'current_user': user, 'patient': patient, 'doctor': doctor}


# Authentication Routes

@app.route('/login')
def login():
    return render_template('login.html')


@app.route('/login/patient', methods=['POST'])
def login_patient():
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        return render_template('login.html', error='Email and password required'), 400
    
    if DB_BACKEND == 'sqlite':
        user = User.query.filter_by(email=email, role='patient').first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['role'] = 'patient'
            return redirect(url_for('patient_dashboard'))
    else:
        user = mongo.db.users.find_one({'email': email, 'role': 'patient'})
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = str(user['_id'])
            session['role'] = 'patient'
            return redirect(url_for('patient_dashboard'))
    
    return render_template('login.html', error='Invalid email or password'), 401


@app.route('/login/doctor', methods=['POST'])
def login_doctor():
    email = request.form.get('email')
    password = request.form.get('password')
    
    if not email or not password:
        return render_template('login.html', error='Email and password required'), 400
    
    if DB_BACKEND == 'sqlite':
        user = User.query.filter_by(email=email, role='doctor').first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['role'] = 'doctor'
            return redirect(url_for('doctor_dashboard'))
    else:
        user = mongo.db.users.find_one({'email': email, 'role': 'doctor'})
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = str(user['_id'])
            session['role'] = 'doctor'
            return redirect(url_for('doctor_dashboard'))
    
    return render_template('login.html', error='Invalid email or password'), 401


@app.route('/signup/patient', methods=['GET', 'POST'])
def signup_patient():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([name, email, phone, password, confirm_password]):
            return render_template('signup_patient.html', error='All fields required'), 400
        
        if password != confirm_password:
            return render_template('signup_patient.html', error='Passwords do not match'), 400
        
        if DB_BACKEND == 'sqlite':
            if User.query.filter_by(email=email).first():
                return render_template('signup_patient.html', error='Email already registered'), 400
            if Patient.query.filter_by(phone=phone).first():
                return render_template('signup_patient.html', error='Phone number already registered'), 400
            
            user = User(email=email, role='patient')
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            patient = Patient(user_id=user.id, name=name, phone=phone, email=email)
            db.session.add(patient)
            db.session.commit()
            
            session['user_id'] = user.id
        else:
            try:
                if mongo.db.users.find_one({'email': email}):
                    return render_template('signup_patient.html', error='Email already registered'), 400
                if mongo.db.patients.find_one({'phone': phone}):
                    return render_template('signup_patient.html', error='Phone number already registered'), 400
                
                res = mongo.db.users.insert_one({
                    'email': email,
                    'password_hash': generate_password_hash(password),
                    'role': 'patient',
                    'created_at': datetime.utcnow()
                })
                user_id = str(res.inserted_id)
                
                mongo.db.patients.insert_one({
                    'user_id': user_id,
                    'name': name,
                    'phone': phone,
                    'email': email
                })
                
                session['user_id'] = user_id
            except Exception as e:
                return render_template('signup_patient.html', error=f'Database Connection Failed! Please allow "0.0.0.0/0" in your MongoDB Atlas Network Access setting. Details: {str(e)[:50]}'), 500
            
        session['role'] = 'patient'
        return redirect(url_for('patient_dashboard'))
    
    return render_template('signup_patient.html')


@app.route('/signup/doctor', methods=['GET', 'POST'])
def signup_doctor():
    if DB_BACKEND == 'sqlite':
        departments = Department.query.all()
    else:
        departments = list(mongo.db.departments.find({}))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        department_id = request.form.get('department_id')
        daily_slot_limit = request.form.get('daily_slot_limit', 10)
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if not all([name, email, department_id, password, confirm_password]):
            return render_template('signup_doctor.html', error='All fields required', departments=departments), 400
        
        if password != confirm_password:
            return render_template('signup_doctor.html', error='Passwords do not match', departments=departments), 400
        
        if DB_BACKEND == 'sqlite':
            if User.query.filter_by(email=email).first():
                return render_template('signup_doctor.html', error='Email already registered', departments=departments), 400
            
            # Create user and doctor
            user = User(email=email, role='doctor')
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            
            doctor = Doctor(user_id=user.id, name=name, department_id=int(department_id), daily_slot_limit=int(daily_slot_limit))
            db.session.add(doctor)
            db.session.commit()
            
            session['user_id'] = user.id
        else:
            if mongo.db.users.find_one({'email': email}):
                return render_template('signup_doctor.html', error='Email already registered', departments=departments), 400
            
            res = mongo.db.users.insert_one({
                'email': email,
                'password_hash': generate_password_hash(password),
                'role': 'doctor',
                'created_at': datetime.utcnow()
            })
            user_id = str(res.inserted_id)
            
            cur = mongo.db.doctors.find_one(sort=[('id', -1)])
            nid = (cur['id'] if cur else 0) + 1
            
            mongo.db.doctors.insert_one({
                'id': nid,
                'user_id': user_id,
                'name': name,
                'department_id': int(department_id),
                'daily_slot_limit': int(daily_slot_limit)
            })
            session['user_id'] = user_id
            
        session['role'] = 'doctor'
        return redirect(url_for('doctor_dashboard'))
    
    return render_template('signup_doctor.html', departments=departments)


@app.route('/patient/dashboard')
def patient_dashboard():
    if 'user_id' not in session or session.get('role') != 'patient':
        return redirect(url_for('login'))
    
    if DB_BACKEND == 'sqlite':
        user = User.query.get(session.get('user_id'))
        patient = Patient.query.filter_by(user_id=user.id).first()
        if not patient:
            return redirect(url_for('login'))
        appointments = Appointment.query.filter_by(patient_id=patient.id).all()
    else:
        from bson.objectid import ObjectId
        user = mongo.db.users.find_one({'_id': ObjectId(session.get('user_id'))})
        patient = mongo.db.patients.find_one({'user_id': str(user['_id'])}) if user else None
        if not patient:
            return redirect(url_for('login'))
        
        appts_cursor = mongo.db.appointments.find({'patient_id': str(patient['_id'])})
        appointments = []
        for a in appts_cursor:
            a['id'] = str(a.get('_id'))
            doc = mongo.db.doctors.find_one({'id': a['doctor_id']})
            if doc:
                dept = mongo.db.departments.find_one({'id': doc.get('department_id')})
                doc['department'] = dept
            a['doctor'] = doc
            appointments.append(a)
            
    return render_template('patient_dashboard.html', patient=patient, appointments=appointments)


@app.route('/doctor/dashboard')
def doctor_dashboard():
    if 'user_id' not in session or session.get('role') != 'doctor':
        return redirect(url_for('login'))
    
    if DB_BACKEND == 'sqlite':
        user = User.query.get(session.get('user_id'))
        doctor = Doctor.query.filter_by(user_id=user.id).first()
        if not doctor:
            return redirect(url_for('login'))
        appointments = Appointment.query.filter_by(doctor_id=doctor.id).all()
    else:
        from bson.objectid import ObjectId
        user = mongo.db.users.find_one({'_id': ObjectId(session.get('user_id'))})
        doctor = mongo.db.doctors.find_one({'user_id': str(user['_id'])}) if user else None
        if not doctor:
            return redirect(url_for('login'))
            
        dept = mongo.db.departments.find_one({'id': doctor.get('department_id')})
        if doctor:
            doctor['department'] = dept
        
        appts_cursor = mongo.db.appointments.find({'doctor_id': doctor['id']})
        appointments = []
        for a in appts_cursor:
            a['id'] = str(a.get('_id'))
            pat = mongo.db.patients.find_one({'_id': ObjectId(a['patient_id'])})
            if pat:
                a['patient'] = pat
            appointments.append(a)
            
    return render_template('doctor_dashboard.html', doctor=doctor, appointments=appointments)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))


@app.route('/')
def index():
    return render_template('index.html')

# simple diagnostic route to show which backend is active (useful for
# debugging environment variable issues)
@app.route('/_debug_backend')
def debug_backend():
    return jsonify({'DB_BACKEND': DB_BACKEND})


@app.route('/book')
def book_page():
    if DB_BACKEND == 'sqlite':
        symptoms = Symptom.query.all()
    else:
        try:
            symptoms = list(mongo.db.symptoms.find({}))
        except Exception as e:
            return f"""
            <h3>Database Connection Failed</h3>
            <p>Vercel could not securely interact with your MongoDB Server.</p>
            <p><b>Reasons:</b> Either your MongoDB IP Whitelist isn't set to "0.0.0.0/0", or your MONGODB_URI is invalid.</p>
            <p><b>Exact Error:</b> {str(e)}</p>
            """, 500
            
    return render_template('book.html', symptoms=symptoms)


@app.route('/admin')
def admin_page():
    if DB_BACKEND == 'sqlite':
        departments = Department.query.all()
        doctors = Doctor.query.all()
        symptoms = Symptom.query.all()
    else:
        try:
            departments = list(mongo.db.departments.find({}))
            doctors = list(mongo.db.doctors.find({}))
            symptoms = list(mongo.db.symptoms.find({}))
        except Exception as e:
            return f"""
            <h3>Database Connection Failed</h3>
            <p>Vercel could not securely interact with your MongoDB Server.</p>
            <p><b>Reasons:</b> Either your MongoDB IP Whitelist isn't set to "0.0.0.0/0", or your MONGODB_URI is invalid.</p>
            <p><b>Exact Error:</b> {str(e)}</p>
            """, 500
            
    return render_template('admin.html', departments=departments, doctors=doctors, symptoms=symptoms)


@app.route('/api/recommend', methods=['POST'])
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


@app.route('/api/book', methods=['POST'])
def book():
    data = request.json or {}
    patient_name = data.get('name')
    phone = data.get('phone')
    email = data.get('email')
    doctor_id = data.get('doctor_id')
    date_str = data.get('date')
    appointment_type = data.get('appointment_type', 'in-person')  # 'in-person' or 'telehealth'

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

        appt = Appointment(patient_id=patient.id, doctor_id=doctor.id, date=str(appt_date), time=data.get('time', ''), status='scheduled', appointment_type=appointment_type)
        db.session.add(appt)
        db.session.commit()

        # Generate telehealth link if telehealth appointment
        telehealth_url = None
        telehealth_passcode = None
        if appointment_type == 'telehealth':
            telehealth_url, telehealth_passcode = generate_telehealth_link(appt.id)
            appt.telehealth_url = telehealth_url
            appt.telehealth_passcode = telehealth_passcode
            db.session.commit()

        # Send booking confirmation notification
        if patient.user_id:
            msg = f'Your appointment with {doctor.name} on {appt_date} has been confirmed.'
            if telehealth_url:
                msg += f' Telehealth link: {telehealth_url} (Passcode: {telehealth_passcode})'
            create_notification(patient.user_id, 'Appointment Confirmed', msg, 'appointment')

        result = {'success': True, 'message': 'Appointment booked', 'appointment_id': appt.id}
        if telehealth_url:
            result['telehealth_url'] = telehealth_url
            result['telehealth_passcode'] = telehealth_passcode
        return jsonify(result)
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

        # Generate telehealth link if requested
        temp_id = str(uuid.uuid4().hex[:12])
        telehealth_url = None
        telehealth_passcode = None
        if appointment_type == 'telehealth':
            telehealth_url, telehealth_passcode = generate_telehealth_link(temp_id)

        appt = {
            'patient_id': patient_id,
            'doctor_id': doctor['id'],
            'date': str(appt_date),
            'time': data.get('time', ''),
            'status': 'scheduled',
            'appointment_type': appointment_type,
            'telehealth_url': telehealth_url,
            'telehealth_passcode': telehealth_passcode,
            'created_at': datetime.utcnow()
        }

        res = mongo.db.appointments.insert_one(appt)

        # Send booking confirmation notification
        patient_doc = mongo.db.patients.find_one({'_id': ObjectId(patient_id)}) if not patient else patient
        if patient_doc and patient_doc.get('user_id'):
            msg = f'Your appointment with {doctor["name"]} on {appt_date} has been confirmed.'
            if telehealth_url:
                msg += f' Telehealth link: {telehealth_url} (Passcode: {telehealth_passcode})'
            create_notification(patient_doc['user_id'], 'Appointment Confirmed', msg, 'appointment')

        result = {'success': True, 'message': 'Appointment booked', 'appointment_id': str(res.inserted_id)}
        if telehealth_url:
            result['telehealth_url'] = telehealth_url
            result['telehealth_passcode'] = telehealth_passcode
        return jsonify(result)


# Admin CRUD APIs


@app.route('/api/admin/departments', methods=['GET', 'POST'])
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


@app.route('/api/admin/departments/<int:dept_id>', methods=['PUT', 'DELETE'])
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


@app.route('/api/admin/symptoms', methods=['GET', 'POST'])
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


@app.route('/api/admin/symptoms/<int:sym_id>', methods=['PUT', 'DELETE'])
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


@app.route('/api/admin/doctors', methods=['GET', 'POST'])
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


@app.route('/api/admin/doctors/<int:doc_id>', methods=['PUT', 'DELETE'])
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
@app.route('/api/appointments', methods=['GET'])
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


@app.route('/api/appointments/export', methods=['GET'])
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


# ============================================================
# UTILITY: Telehealth URL & Passcode Generator
# ============================================================
def generate_telehealth_link(appointment_id):
    """Generate a deterministic but unique telehealth meeting URL and passcode."""
    raw = f"{appointment_id}-{uuid.uuid4().hex}"
    meeting_hash = hashlib.sha256(raw.encode()).hexdigest()[:12]
    passcode = hashlib.md5(raw.encode()).hexdigest()[:6].upper()
    url = f"/telehealth/meeting/{meeting_hash}"
    return url, passcode


# ============================================================
# UTILITY: Notification Creator
# ============================================================
def create_notification(user_id, title, message, category='info'):
    """Push an in-app notification for a user (both SQLite and MongoDB)."""
    try:
        if DB_BACKEND == 'sqlite':
            notif = Notification(user_id=user_id, title=title, message=message, category=category)
            db.session.add(notif)
            db.session.commit()
        else:
            mongo.db.notifications.insert_one({
                'user_id': str(user_id),
                'title': title,
                'message': message,
                'category': category,
                'is_read': False,
                'created_at': datetime.utcnow()
            })
    except Exception as e:
        print(f'Notification creation failed: {e}')


# ============================================================
# FEATURE 1: Digital Prescriptions & Medical Records
# ============================================================

@app.route('/api/appointments/<appt_id>/prescription', methods=['POST'])
def create_prescription(appt_id):
    """Doctor writes a prescription for a completed or in-progress appointment."""
    if 'user_id' not in session or session.get('role') != 'doctor':
        return jsonify({'success': False, 'message': 'Unauthorized: doctor login required'}), 403

    data = request.json or {}
    diagnosis = data.get('diagnosis')
    medicines = data.get('medicines')
    notes = data.get('notes', '')
    lab_tests = data.get('lab_tests', '')

    if not diagnosis or not medicines:
        return jsonify({'success': False, 'message': 'Diagnosis and medicines are required'}), 400

    if DB_BACKEND == 'sqlite':
        appt = Appointment.query.get(int(appt_id))
        if not appt:
            return jsonify({'success': False, 'message': 'Appointment not found'}), 404

        rx = Prescription(
            appointment_id=appt.id,
            diagnosis=diagnosis,
            medicines=medicines,
            notes=notes,
            lab_tests=lab_tests
        )
        db.session.add(rx)
        db.session.commit()

        # Notify the patient
        patient = Patient.query.get(appt.patient_id)
        if patient and patient.user_id:
            doctor = Doctor.query.get(appt.doctor_id)
            create_notification(
                patient.user_id,
                'New Prescription Issued',
                f'{doctor.name if doctor else "Your doctor"} has issued a new prescription for your appointment on {appt.date}.',
                'prescription'
            )

        return jsonify({'success': True, 'prescription_id': rx.id})
    else:
        from bson.objectid import ObjectId
        appt = mongo.db.appointments.find_one({'_id': ObjectId(appt_id)})
        if not appt:
            return jsonify({'success': False, 'message': 'Appointment not found'}), 404

        rx_doc = {
            'appointment_id': appt_id,
            'diagnosis': diagnosis,
            'medicines': medicines,
            'notes': notes,
            'lab_tests': lab_tests,
            'created_at': datetime.utcnow()
        }
        res = mongo.db.prescriptions.insert_one(rx_doc)

        # Notify patient
        patient = mongo.db.patients.find_one({'_id': ObjectId(appt['patient_id'])})
        if patient and patient.get('user_id'):
            doctor = mongo.db.doctors.find_one({'id': appt['doctor_id']})
            create_notification(
                patient['user_id'],
                'New Prescription Issued',
                f'{doctor["name"] if doctor else "Your doctor"} has issued a new prescription for your appointment on {appt["date"]}.',
                'prescription'
            )

        return jsonify({'success': True, 'prescription_id': str(res.inserted_id)})


@app.route('/api/appointments/<appt_id>/prescription', methods=['GET'])
def get_prescription(appt_id):
    """Retrieve prescriptions for a specific appointment."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required'}), 403

    if DB_BACKEND == 'sqlite':
        rxs = Prescription.query.filter_by(appointment_id=int(appt_id)).all()
        return jsonify([{
            'id': rx.id,
            'diagnosis': rx.diagnosis,
            'medicines': rx.medicines,
            'notes': rx.notes,
            'lab_tests': rx.lab_tests,
            'created_at': str(rx.created_at)
        } for rx in rxs])
    else:
        rxs = list(mongo.db.prescriptions.find({'appointment_id': appt_id}))
        return jsonify([{
            'id': str(rx['_id']),
            'diagnosis': rx.get('diagnosis'),
            'medicines': rx.get('medicines'),
            'notes': rx.get('notes'),
            'lab_tests': rx.get('lab_tests'),
            'created_at': str(rx.get('created_at'))
        } for rx in rxs])


@app.route('/api/patient/records', methods=['GET'])
def patient_medical_records():
    """Patient retrieves their full medical history (all prescriptions)."""
    if 'user_id' not in session or session.get('role') != 'patient':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403

    if DB_BACKEND == 'sqlite':
        user = User.query.get(session['user_id'])
        patient = Patient.query.filter_by(user_id=user.id).first()
        if not patient:
            return jsonify([])
        appts = Appointment.query.filter_by(patient_id=patient.id).all()
        records = []
        for appt in appts:
            rxs = Prescription.query.filter_by(appointment_id=appt.id).all()
            doctor = Doctor.query.get(appt.doctor_id)
            for rx in rxs:
                records.append({
                    'appointment_date': appt.date,
                    'doctor': doctor.name if doctor else 'Unknown',
                    'diagnosis': rx.diagnosis,
                    'medicines': rx.medicines,
                    'notes': rx.notes,
                    'lab_tests': rx.lab_tests,
                    'created_at': str(rx.created_at)
                })
        return jsonify(records)
    else:
        from bson.objectid import ObjectId
        user = mongo.db.users.find_one({'_id': ObjectId(session['user_id'])})
        patient = mongo.db.patients.find_one({'user_id': str(user['_id'])}) if user else None
        if not patient:
            return jsonify([])
        appts = list(mongo.db.appointments.find({'patient_id': str(patient['_id'])}))
        records = []
        for appt in appts:
            rxs = list(mongo.db.prescriptions.find({'appointment_id': str(appt['_id'])}))
            doctor = mongo.db.doctors.find_one({'id': appt.get('doctor_id')})
            for rx in rxs:
                records.append({
                    'appointment_date': appt.get('date'),
                    'doctor': doctor.get('name') if doctor else 'Unknown',
                    'diagnosis': rx.get('diagnosis'),
                    'medicines': rx.get('medicines'),
                    'notes': rx.get('notes'),
                    'lab_tests': rx.get('lab_tests'),
                    'created_at': str(rx.get('created_at'))
                })
        return jsonify(records)


# ============================================================
# FEATURE 2: Appointment Status & Queue Workflow
# ============================================================

VALID_STATUS_TRANSITIONS = {
    'scheduled': ['waiting-room', 'cancelled'],
    'waiting-room': ['in-consultation', 'cancelled'],
    'in-consultation': ['completed'],
    'completed': [],
    'cancelled': []
}


@app.route('/api/appointments/<appt_id>/status', methods=['PUT'])
def update_appointment_status(appt_id):
    """Update appointment status through the workflow pipeline."""
    if 'user_id' not in session or session.get('role') != 'doctor':
        return jsonify({'success': False, 'message': 'Unauthorized: doctor login required'}), 403

    data = request.json or {}
    new_status = data.get('status')

    if not new_status:
        return jsonify({'success': False, 'message': 'Status is required'}), 400

    if DB_BACKEND == 'sqlite':
        appt = Appointment.query.get(int(appt_id))
        if not appt:
            return jsonify({'success': False, 'message': 'Appointment not found'}), 404

        current = appt.status or 'scheduled'
        allowed = VALID_STATUS_TRANSITIONS.get(current, [])
        if new_status not in allowed:
            return jsonify({'success': False, 'message': f'Cannot transition from "{current}" to "{new_status}". Allowed: {allowed}'}), 400

        appt.status = new_status
        db.session.commit()

        # Notify patient of status change
        patient = Patient.query.get(appt.patient_id)
        if patient and patient.user_id:
            status_messages = {
                'waiting-room': 'You have been checked in. Please proceed to the waiting room.',
                'in-consultation': 'The doctor is ready for you. Your consultation is starting.',
                'completed': 'Your appointment has been completed. Check your dashboard for prescriptions.',
                'cancelled': 'Your appointment has been cancelled.'
            }
            create_notification(
                patient.user_id,
                f'Appointment Status: {new_status.replace("-", " ").title()}',
                status_messages.get(new_status, f'Your appointment status has been updated to {new_status}.'),
                'appointment'
            )

        return jsonify({'success': True, 'status': new_status})
    else:
        from bson.objectid import ObjectId
        appt = mongo.db.appointments.find_one({'_id': ObjectId(appt_id)})
        if not appt:
            return jsonify({'success': False, 'message': 'Appointment not found'}), 404

        current = appt.get('status', 'scheduled')
        allowed = VALID_STATUS_TRANSITIONS.get(current, [])
        if new_status not in allowed:
            return jsonify({'success': False, 'message': f'Cannot transition from "{current}" to "{new_status}". Allowed: {allowed}'}), 400

        mongo.db.appointments.update_one({'_id': ObjectId(appt_id)}, {'$set': {'status': new_status}})

        # Notify patient
        patient = mongo.db.patients.find_one({'_id': ObjectId(appt['patient_id'])})
        if patient and patient.get('user_id'):
            status_messages = {
                'waiting-room': 'You have been checked in. Please proceed to the waiting room.',
                'in-consultation': 'The doctor is ready for you. Your consultation is starting.',
                'completed': 'Your appointment has been completed. Check your dashboard for prescriptions.',
                'cancelled': 'Your appointment has been cancelled.'
            }
            create_notification(
                patient['user_id'],
                f'Appointment Status: {new_status.replace("-", " ").title()}',
                status_messages.get(new_status, f'Your appointment status has been updated to {new_status}.'),
                'appointment'
            )

        return jsonify({'success': True, 'status': new_status})


# ============================================================
# FEATURE 3: Telemedicine — telehealth meeting room
# ============================================================

@app.route('/telehealth/meeting/<meeting_hash>')
def telehealth_meeting(meeting_hash):
    """Render a simple telehealth meeting placeholder page."""
    return render_template('telehealth.html', meeting_hash=meeting_hash)


# ============================================================
# FEATURE 4: Notification System
# ============================================================

@app.route('/api/notifications', methods=['GET'])
def get_notifications():
    """Retrieve all notifications for the logged-in user."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required'}), 403

    if DB_BACKEND == 'sqlite':
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
        notifs = list(mongo.db.notifications.find({'user_id': str(session['user_id'])}).sort('created_at', -1))
        return jsonify([{
            'id': str(n['_id']),
            'title': n.get('title'),
            'message': n.get('message'),
            'category': n.get('category'),
            'is_read': n.get('is_read', False),
            'created_at': str(n.get('created_at'))
        } for n in notifs])


@app.route('/api/notifications/<notif_id>/read', methods=['PUT'])
def mark_notification_read(notif_id):
    """Mark a single notification as read."""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Login required'}), 403

    if DB_BACKEND == 'sqlite':
        notif = Notification.query.get(int(notif_id))
        if not notif or notif.user_id != session['user_id']:
            return jsonify({'success': False}), 404
        notif.is_read = True
        db.session.commit()
        return jsonify({'success': True})
    else:
        from bson.objectid import ObjectId
        mongo.db.notifications.update_one(
            {'_id': ObjectId(notif_id), 'user_id': str(session['user_id'])},
            {'$set': {'is_read': True}}
        )
        return jsonify({'success': True})


@app.route('/api/notifications/unread-count', methods=['GET'])
def unread_notification_count():
    """Return the count of unread notifications for the logged-in user."""
    if 'user_id' not in session:
        return jsonify({'count': 0})

    if DB_BACKEND == 'sqlite':
        count = Notification.query.filter_by(user_id=session['user_id'], is_read=False).count()
    else:
        count = mongo.db.notifications.count_documents({'user_id': str(session['user_id']), 'is_read': False})
    return jsonify({'count': count})


if __name__ == '__main__':
    # Initialize/seed DB before starting server
    if DB_BACKEND == 'sqlite':
        try:
            with app.app_context():
                init_sqlite_db()
        except Exception as e:
            print('Warning: SQLite DB initialization failed:', e)
    else:
        try:
            from db_init import init_db
            init_db(mongo)
        except Exception as e:
            print('Warning: MongoDB initialization failed:', e)

    # In development we used to run with debug=True which enables the
    # reloader.  Unfortunately the reloader spawns a child process which
    # doesn't inherit our custom DB_BACKEND environment variable, causing
    # the child to default back to MongoDB and then hang when it cannot
    # reach Atlas.  To keep behaviour predictable we disable the reloader
    # and only turn on debugging if FLASK_DEBUG is explicitly set.
    debug_mode = os.getenv('FLASK_DEBUG', '0') == '1'
    app.run(debug=debug_mode, use_reloader=False)
